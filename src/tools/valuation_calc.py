"""
企業価値計算ツール (DCF法・PER法)
Agent6 (統括マネージャー) が使用する。LLMには計算をさせない。
"""
import json as _json
import statistics
from crewai.tools import BaseTool
from pydantic import BaseModel, field_validator
from loguru import logger

from src.config import DCF_DEFAULTS


def _format_jpy(value: float) -> str:
    """円単位の値を『○兆○,○○○億円』の日本語表記に変換する（LLMの桁誤読を防ぐため）。"""
    if value < 0:
        return f"-{_format_jpy(-value)}"
    cho = int(value // 1_000_000_000_000)
    oku = int((value % 1_000_000_000_000) // 100_000_000)
    if cho > 0:
        return f"{cho}兆{oku:,}億円"
    else:
        return f"{oku:,}億円"


# ===== DCF法 =====

class DCFInput(BaseModel):
    free_cash_flows: list[float]       # 過去のFCF（直近3〜5年・古い順）
    revenue_cagr: float                # 売上CAGR（Agent4から）。segment_weightsとsegment_growth_ratesが揃っている場合は無視される。
    operating_margin: float            # 営業利益率（Agent3から）
    shares_outstanding: float          # 発行済株式数
    net_debt: float                    # 純有利子負債（負なら純現金）
    tax_rate: float = DCF_DEFAULTS["tax_rate"]
    capex_ratio: float = DCF_DEFAULTS["capex_ratio"]
    risk_free_rate: float = DCF_DEFAULTS["risk_free_rate"]
    equity_risk_premium: float = DCF_DEFAULTS["equity_risk_premium"]
    beta: float = DCF_DEFAULTS["beta"]
    debt_cost: float = DCF_DEFAULTS["debt_cost"]
    debt_ratio: float = DCF_DEFAULTS["debt_ratio"]
    terminal_growth_rate: float = DCF_DEFAULTS["terminal_growth_rate"]
    projection_years: int = DCF_DEFAULTS["projection_years"]
    # セグメント別成長率（提供時はrevenue_cagrの代わりに加重平均で計算）
    segment_names: list[str] = []         # セグメント名（例: ["エンバイロメント", "デジタル"]）
    segment_weights: list[float] = []     # 売上構成比（0-1、合計1.0）
    segment_growth_rates: list[float] = [] # 各セグメントの成長率（年率）
    # セグメントミックス変化による利益率ドリフト（デフォルト0.0 = 既存挙動と完全一致）
    # projected_fcf[t] = base_fcf * (1+growth)^t * (1+margin_drift)^t
    # 例: 低利益セグメント拡大 → -0.01〜-0.02 / 高利益セグメント拡大 → +0.01〜+0.02
    margin_drift: float = 0.0

    @field_validator('free_cash_flows', 'segment_weights', 'segment_growth_rates', mode='before')
    @classmethod
    def _parse_float_list(cls, v):
        """LLMがJSON文字列またはカンマ区切り文字列で渡した場合も正しく解析する。"""
        if isinstance(v, str):
            try:
                return [float(x) for x in _json.loads(v)]
            except Exception:
                try:
                    return [float(x.strip()) for x in v.split(',') if x.strip()]
                except Exception:
                    return []
        if isinstance(v, list):
            return [float(x) for x in v if x is not None]
        return v

    @field_validator('segment_names', mode='before')
    @classmethod
    def _parse_str_list(cls, v):
        """segment_namesがJSON文字列で渡された場合も正しく解析する。"""
        if isinstance(v, str):
            try:
                return _json.loads(v)
            except Exception:
                return [x.strip() for x in v.split(',') if x.strip()]
        return v


# ===== マルチプル法 =====

class MultiplesInput(BaseModel):
    target_eps: float                      # 対象企業EPS（Agent3から）
    peer_pers: list[float]                 # 同業他社のPER一覧（Agent2から）
    # EV/EBITDA法（オプション: 事業構造が異なる企業比較に有効）
    target_ebitda: float = 0.0            # 対象企業EBITDA（Agent3のFinancialCalcToolから）
    target_net_debt: float = 0.0          # 対象企業の純有利子負債（Agent3から）
    target_shares: float = 0.0            # 対象企業の発行済株式数（Agent3から）
    peer_ev_ebitdas: list[float] = []     # 同業他社のEV/EBITDA一覧（Agent2から）
    # セグメント別加重PER（異質セグメントを混在させない補正）
    # 提供時はpeer_persの全体中央値の代わりにセグメント加重PERを使用する
    # 例: 自動車(60%,PER13倍) + 半導体(40%,PER25倍) → 加重PER=17.8倍
    segment_names: list[str] = []          # セグメント名（例: ["自動車", "半導体"]）
    segment_weights: list[float] = []      # 売上構成比（0-1）
    segment_median_pers: list[float] = []  # 各セグメント競合のPER中央値（Agent2が収集）

    @field_validator('peer_pers', 'peer_ev_ebitdas', 'segment_weights', 'segment_median_pers', mode='before')
    @classmethod
    def _parse_float_list(cls, v):
        """LLMがJSON文字列またはカンマ区切り文字列で渡した場合も正しく解析する。"""
        if isinstance(v, str):
            try:
                return [float(x) for x in _json.loads(v)]
            except Exception:
                try:
                    return [float(x.strip()) for x in v.split(',') if x.strip()]
                except Exception:
                    return []
        if isinstance(v, list):
            return [float(x) for x in v if x is not None]
        return v

    @field_validator('segment_names', mode='before')
    @classmethod
    def _parse_str_list(cls, v):
        """segment_namesがJSON文字列で渡された場合も正しく解析する。"""
        if isinstance(v, str):
            try:
                return _json.loads(v)
            except Exception:
                return [x.strip() for x in v.split(',') if x.strip()]
        return v


class DCFValuationTool(BaseTool):
    """
    DCF法で企業価値と理論株価を計算する。
    """
    name: str = "DCFValuationTool"
    description: str = (
        "DCF法で企業価値と理論株価をPythonで計算する。Agent6が使用する。\n"
        "【超重要・単位の統一】\n"
        "金額パラメータ（free_cash_flows, net_debtなど）は必ず【実際の円単位（1円単位）】に換算して入力すること！\n"
        "（例: 3,003,519百万円 → 3003519000000）。shares_outstanding は単元（株）そのままで入力。"
    )
    args_schema: type[BaseModel] = DCFInput

    def _run(self, **kwargs) -> dict:
        try:
            p = DCFInput(**kwargs)
        except Exception as e:
            return {"error": f"入力パラメータエラー: {e}"}

        if not p.free_cash_flows:
            return {"error": "free_cash_flows が空です"}

        # FCF規模チェック: 正のFCFが極端にばらついている場合に四半期データ混入等を警告
        _pos_fcfs = [f for f in p.free_cash_flows if f > 0]
        _fcf_scale_warning = ""
        if len(_pos_fcfs) >= 2:
            _min_fcf, _max_fcf = min(_pos_fcfs), max(_pos_fcfs)
            if _max_fcf > 0 and _min_fcf / _max_fcf < 0.1:
                _fcf_scale_warning = (
                    f"⚠️ FCF異常値警告: 入力FCFの最小値({_format_jpy(_min_fcf)})が"
                    f"最大値({_format_jpy(_max_fcf)})の10%未満です。"
                    "四半期データの混入・単位ミス（百万円単位入力等）を確認してください。"
                )
                logger.warning(_fcf_scale_warning)

        # WACC計算 (CAPM)
        note = ""  # 各種警告・注記を格納（後でresに追加）
        re = p.risk_free_rate + p.beta * p.equity_risk_premium
        wacc = (1 - p.debt_ratio) * re + p.debt_ratio * p.debt_cost * (1 - p.tax_rate)

        # WACC低水準警告（日本株の一般的な範囲 5〜7% を大きく下回る場合）
        if wacc < 0.045:
            note += (
                f"\n⚠️ WACC({wacc:.2%})警告: 日本株では電力・公益セクターでも5〜7%程度が一般的です。"
                "risk_free_rate・equity_risk_premium・betaの入力値を再確認してください。"
                "（例: 国債利回り1.5%、ERP 6%、β=1.1 → WACC≒5.88%）"
            )

        if wacc <= p.terminal_growth_rate:
            logger.warning("WACC <= 永久成長率。継続価値計算が不安定になるため調整します")
            wacc = p.terminal_growth_rate + 0.01

        # 成長率の決定：セグメント別データが揃っている場合は加重平均CAGRを使用
        growth_rate = p.revenue_cagr
        segment_cagr_note = ""
        if (p.segment_weights and p.segment_growth_rates
                and len(p.segment_weights) == len(p.segment_growth_rates)):
            weighted_cagr = sum(w * g for w, g in zip(p.segment_weights, p.segment_growth_rates))
            growth_rate = weighted_cagr
            details = []
            for i, (w, g) in enumerate(zip(p.segment_weights, p.segment_growth_rates)):
                name = p.segment_names[i] if i < len(p.segment_names) else f"セグメント{i+1}"
                details.append(f"{name}: {g*100:.1f}%×{w*100:.0f}%")
            segment_cagr_note = f"加重平均CAGR={weighted_cagr*100:.2f}% ({', '.join(details)})"
            logger.info(f"セグメント別加重平均CAGRを使用: {segment_cagr_note}")

        # 直近FCFをベースに将来FCFを予測
        # (1+margin_drift)^t でセグメントミックス変化による利益率変動を反映
        # margin_drift=0.0 のとき既存と完全一致（後方互換）
        base_fcf = p.free_cash_flows[-1]
        projected_fcfs = [
            base_fcf * (1 + growth_rate) ** t * (1 + p.margin_drift) ** t
            for t in range(1, p.projection_years + 1)
        ]
        margin_drift_note = ""
        if p.margin_drift != 0.0:
            if abs(p.margin_drift) > 0.05:
                logger.warning(f"margin_drift={p.margin_drift:.3f} が±5%/年を超えています。入力値を確認してください。")
            margin_drift_note = f"利益率ドリフト={p.margin_drift*100:+.1f}%/年（セグメントミックス変化を反映）"
            logger.info(f"margin_driftを適用: {margin_drift_note}")

        # FCFの現在価値
        pv_fcfs = sum(
            fcf / (1 + wacc) ** t
            for t, fcf in enumerate(projected_fcfs, 1)
        )

        # 継続価値 (Gordon Growth Model)
        terminal_fcf = projected_fcfs[-1] * (1 + p.terminal_growth_rate)
        tv = terminal_fcf / (wacc - p.terminal_growth_rate)
        pv_tv = tv / (1 + wacc) ** p.projection_years

        # 株式価値
        enterprise_value = pv_fcfs + pv_tv
        equity_value = enterprise_value - p.net_debt
        intrinsic_price = equity_value / p.shares_outstanding if p.shares_outstanding else None
        
        # 継続価値の割合（計算の妥当性チェック用）
        tv_ratio = pv_tv / enterprise_value if enterprise_value else 0

        # 単位不整合（百万円単位入力）の自動補正
        # 通常、上場企業の企業価値(円)は発行済株式数(株)よりも十分に大きくなります（理論株価が1円未満になることは稀）。
        # もし企業価値の数値自体が株数より小さい場合、1,000,000倍の単位ミス（百万円単位での入力）と判定して補正します。
        scale_factor = 1  # 感応度分析のnet_debt補正に使用
        if p.shares_outstanding and p.shares_outstanding > 100_000:
            if enterprise_value < p.shares_outstanding:
                logger.warning("DCF企業価値が発行済株式数より小さいため、入力値が『百万円単位』と判定し、1,000,000倍に自動補正します。")
                scale_factor = 1_000_000
                if intrinsic_price is not None:
                    intrinsic_price *= 1_000_000
                enterprise_value *= 1_000_000
                equity_value *= 1_000_000
                pv_fcfs *= 1_000_000
                tv *= 1_000_000
                pv_tv *= 1_000_000
                projected_fcfs = [f * 1_000_000 for f in projected_fcfs]
                note += "※入力された財務数値が百万円単位であったため、計算過程で自動的に1,000,000倍（1円単位）に補正して算定しました。"

        if tv_ratio > 0.75:
            if tv_ratio > 0.9:
                note += ("\n※警告【高】: 企業価値の90%超が継続価値で占められています。"
                         "ターミナル前提（永久成長率・WACC）への感応度が極めて高く、算定結果の信頼性は低いです。")
            else:
                note += ("\n※警告【中】: 企業価値の75〜90%が継続価値で占められています（ターミナル頼みのDCF）。"
                         "永久成長率・WACCの前提を慎重に確認してください。")

        # ===== 感応度分析テーブル（WACC × 永久成長率 の 3×5 マトリックス） =====
        # 補正済みの projected_fcfs と scale_factor を使用して各セルの理論株価を計算する
        _wacc_deltas = [-0.01, -0.005, 0.0, +0.005, +0.01]
        _g_deltas    = [+0.005, 0.0, -0.005]
        _net_debt_corrected = p.net_debt * scale_factor

        _sens_rows = []
        for _gd in _g_deltas:
            _row = []
            for _wd in _wacc_deltas:
                _w = wacc + _wd
                _g = p.terminal_growth_rate + _gd
                if _w <= _g:
                    _w = _g + 0.001  # ゼロ除算回避
                _pv_fcfs_s = sum(f / (1 + _w) ** t for t, f in enumerate(projected_fcfs, 1))
                _tv_s = projected_fcfs[-1] * (1 + _g) / (_w - _g)
                _pv_tv_s = _tv_s / (1 + _w) ** p.projection_years
                _ev_s = _pv_fcfs_s + _pv_tv_s
                _eq_s = _ev_s - _net_debt_corrected
                _price_s = _eq_s / p.shares_outstanding if p.shares_outstanding else 0
                _row.append(f"{round(_price_s):,}円" if _price_s > 0 else "N/A")
            _sens_rows.append(_row)

        # Markdown テーブル生成（ヘッダーは実際の % 値）
        _wacc_hdrs = [f"WACC {(wacc + d) * 100:.2f}%" for d in _wacc_deltas]
        _g_labels  = [f"g={(p.terminal_growth_rate + d) * 100:.2f}%" for d in _g_deltas]
        _tbl_header = "| g＼WACC | " + " | ".join(_wacc_hdrs) + " |"
        _tbl_sep    = "|" + "---|" * (len(_wacc_deltas) + 1)
        _tbl_rows   = [f"| {_g_labels[i]} | " + " | ".join(_sens_rows[i]) + " |"
                       for i in range(len(_g_deltas))]
        sensitivity_md = "\n".join([_tbl_header, _tbl_sep] + _tbl_rows)

        res = {
            "method": "DCF法",
            "growth_rate_used": round(growth_rate, 4),
            "wacc": round(wacc, 4),
            "projected_fcfs": [round(f) for f in projected_fcfs],
            # --- 事業価値（予測期間FCFの現在価値合計）---
            "pv_fcfs": round(pv_fcfs),
            "pv_fcfs_label": _format_jpy(pv_fcfs),
            # --- 継続価値 ---
            # ⚠️ terminal_value_undiscounted は「参考値（未割引）」。EV計算には使用しない。
            # ⚠️ レポートに記載する際は必ず pv_terminal_value（割引済み）を使用すること。
            "terminal_value_undiscounted": round(tv),        # 未割引TV（参考値・EV計算に不使用）
            "pv_terminal_value": round(pv_tv),               # 割引済みTV（EV計算に使用）
            "pv_terminal_value_label": _format_jpy(pv_tv),  # 割引済みTVの日本語表記
            "tv_ratio": round(tv_ratio, 4),
            # --- 企業価値 = 事業価値(pv_fcfs) + 継続価値PV(pv_terminal_value) ---
            "enterprise_value": round(enterprise_value),
            "enterprise_value_label": _format_jpy(enterprise_value),
            # LLMの加算ミスを防ぐための検証用文字列
            "ev_composition": (
                f"EV = 事業価値{_format_jpy(pv_fcfs)} + 継続価値PV{_format_jpy(pv_tv)}"
                f" = {_format_jpy(enterprise_value)}"
            ),
            "equity_value": round(equity_value),
            "equity_value_label": _format_jpy(equity_value),
            "intrinsic_price_per_share": round(intrinsic_price, 2) if intrinsic_price else None,
            # --- 感応度分析テーブル ---
            "sensitivity_table_markdown": sensitivity_md,
            "sensitivity_wacc_base": round(wacc, 4),
            "sensitivity_g_base": round(p.terminal_growth_rate, 4),
        }
        if segment_cagr_note:
            res["segment_cagr_note"] = segment_cagr_note
        if margin_drift_note:
            res["margin_drift_note"] = margin_drift_note
        if _fcf_scale_warning:
            res["fcf_scale_warning"] = _fcf_scale_warning
        if note:
            res["note"] = note
        return res


class MultiplesValuationTool(BaseTool):
    """
    マルチプル法（PER法・EV/EBITDA法）で企業価値と理論株価を計算する。
    """
    name: str = "MultiplesValuationTool"
    description: str = (
        "マルチプル法（PER法＋EV/EBITDA法）で理論株価をPythonで計算する。Agent6が使用する。\n"
        "PER法: target_eps（円/株）、peer_pers（倍リスト）を渡すこと。\n"
        "EV/EBITDA法（任意）: target_ebitda・target_net_debt・target_shares・peer_ev_ebitdas も渡すと"
        "事業構造が異なる企業比較にも対応したEV/EBITDA法の理論株価が追加計算される。\n"
        "⚠️ 競合データが不足の場合は勝手に数値を仮定せず、その旨を記載すること。"
    )
    args_schema: type[BaseModel] = MultiplesInput

    def _run(self, **kwargs) -> dict:
        try:
            p = MultiplesInput(**kwargs)
        except Exception as e:
            return {"error": f"入力パラメータエラー: {e}"}

        if not p.peer_pers:
            return {"error": "peer_pers が空です。PER法による算定ができません。"}

        # セグメント加重PERが提供されているか確認
        # 提供時はpeer_persの全体中央値の代わりにセグメント加重PERを優先使用
        segment_weighted_per = None
        segment_per_note = ""
        if (p.segment_weights and p.segment_median_pers
                and len(p.segment_weights) == len(p.segment_median_pers)):
            segment_weighted_per = sum(
                w * per for w, per in zip(p.segment_weights, p.segment_median_pers)
            )
            details = []
            for i, (w, per) in enumerate(zip(p.segment_weights, p.segment_median_pers)):
                name = p.segment_names[i] if i < len(p.segment_names) else f"セグメント{i+1}"
                details.append(f"{name}: PER{per:.1f}倍×{w*100:.0f}%")
            segment_per_note = f"セグメント加重PER={segment_weighted_per:.2f}倍 ({', '.join(details)})"
            logger.info(f"セグメント加重PERを使用: {segment_per_note}")

        # PER法: セグメント加重PERが使える場合はそちらを優先、なければ全体中央値にフォールバック
        median_per = statistics.median(p.peer_pers)
        effective_per = segment_weighted_per if segment_weighted_per is not None else median_per
        per_price = p.target_eps * effective_per

        result = {
            "method": "マルチプル法（PER法＋EV/EBITDA法）",
            "per_method": {
                "median_peer_per": round(median_per, 2),
                "effective_per_used": round(effective_per, 2),
                "per_implied_price": round(per_price, 2),
            },
        }
        if segment_per_note:
            result["per_method"]["segment_weighted_per_note"] = segment_per_note

        # EV/EBITDA法（オプション）
        if p.peer_ev_ebitdas and p.target_ebitda > 0 and p.target_shares > 0:
            median_ev_ebitda = statistics.median(p.peer_ev_ebitdas)
            implied_ev = p.target_ebitda * median_ev_ebitda
            implied_equity = implied_ev - p.target_net_debt
            ev_ebitda_price = implied_equity / p.target_shares
            result["ev_ebitda_method"] = {
                "median_peer_ev_ebitda": round(median_ev_ebitda, 2),
                "implied_ev": round(implied_ev),
                "implied_ev_label": _format_jpy(implied_ev),
                "implied_equity": round(implied_equity),
                "implied_equity_label": _format_jpy(implied_equity),
                "ev_ebitda_implied_price": round(ev_ebitda_price, 2),
            }
        elif p.peer_ev_ebitdas:
            result["ev_ebitda_method"] = {
                "error": "EV/EBITDA法にはtarget_ebitda・target_net_debt・target_sharesも必要です。"
            }

        # ROIC vs WACC バリュートラップ判定（両方 > 0 の場合のみ）
        if p.roic > 0 and p.base_wacc > 0:
            spread = p.roic - p.base_wacc
            if spread < 0:
                result["value_trap_warning"] = (
                    f"⚠️ 価値破壊懸念: ROIC({p.roic:.2%}) < WACC({p.base_wacc:.2%})、"
                    f"スプレッド = {spread:.2%}。"
                    "【重要】この数値をそのままバリュートラップと断定しないこと。"
                    "必ず以下の観点で「一時的低下」か「構造的低収益」かを判断してレポートに記載すること: "
                    "(1)業界サイクル・大型設備投資集中期による一時的ROIC低下の可能性 "
                    "(2)セグメント別ROIC差異（高ROIC事業が低ROIC事業に引き下げられていないか） "
                    "(3)CCC圧縮・遊休資産削減によるROIC改善余地の有無。"
                    "構造的低収益と判断した場合のみ「バリュートラップリスク」として投資判断に反映すること。"
                )
            else:
                result["value_creation_note"] = (
                    f"✅ 価値創造確認: ROIC({p.roic:.2%}) > WACC({p.base_wacc:.2%})。"
                    f"スプレッド = +{spread:.2%}。株主価値を創造しています。"
                )

        return result


# ===== SOTP（Sum-of-the-Parts）法 =====

class SOTPSegment(BaseModel):
    """SOTP 1セグメントの入力定義"""
    name: str
    ebitda: float = 0.0               # セグメントEBITDA（円単位）
    earnings: float = 0.0             # セグメント営業利益/純利益（円単位）。EV/EBITDA不可時のPER法用
    ev_ebitda_multiple: float = 0.0   # EV/EBITDA倍率（Agent2のセグメント別競合中央値）
    per_multiple: float = 0.0         # PER倍率（Agent2の競合中央値）。EV/EBITDA不可時のフォールバック


class SOTPInput(BaseModel):
    segments: list[SOTPSegment]       # セグメントリスト
    net_debt: float                   # 連結純有利子負債（円単位・負なら純現金）
    shares_outstanding: float         # 発行済株式数


class SOTPValuationTool(BaseTool):
    """
    Sum-of-the-Parts（SOTP）法でセグメント別企業価値を合算し、理論株価を算定する。
    複数の異質セグメントを持つ企業（例: 環境事業 + デジタル事業）に有効。
    各セグメントのEBITDAに対してEV/EBITDA倍率を適用（不可なら earnings × PER でフォールバック）。
    """
    name: str = "SOTPValuationTool"
    description: str = (
        "SOTP（Sum-of-the-Parts）法でセグメント別企業価値を合算して理論株価を計算する。\n"
        "Agent6が多セグメント企業に使用する。\n"
        "segments: [{name, ebitda, earnings, ev_ebitda_multiple, per_multiple}]のリスト。\n"
        "net_debt: 連結純有利子負債（円単位）、shares_outstanding: 発行済株式数。\n"
        "各セグメントはEV/EBITDA法を優先、不可の場合はPER法にフォールバック。\n"
        "⚠️ 金額パラメータはすべて【実際の円単位】で入力すること。"
    )
    args_schema: type[BaseModel] = SOTPInput

    def _run(self, **kwargs) -> dict:
        try:
            p = SOTPInput(**kwargs)
        except Exception as e:
            return {"error": f"入力パラメータエラー: {e}"}

        if not p.segments:
            return {"error": "segments が空です"}
        if not p.shares_outstanding:
            return {"error": "shares_outstanding が0です"}

        segment_results = []
        total_ev = 0.0
        warnings = []

        for seg in p.segments:
            # EV/EBITDA法を優先（ebitda と ev_ebitda_multiple が両方 > 0 の場合）
            if seg.ebitda > 0 and seg.ev_ebitda_multiple > 0:
                seg_ev = seg.ebitda * seg.ev_ebitda_multiple
                method = f"EV/EBITDA法 ({seg.ev_ebitda_multiple:.1f}倍)"
            # フォールバック: PER法（earnings と per_multiple が両方 > 0 の場合）
            elif seg.earnings > 0 and seg.per_multiple > 0:
                seg_ev = seg.earnings * seg.per_multiple
                method = f"PER法 ({seg.per_multiple:.1f}倍)"
            else:
                warnings.append(f"「{seg.name}」: ebitda/earnings・倍率のいずれかが0のため算定不能")
                segment_results.append({
                    "name": seg.name,
                    "implied_ev": None,
                    "implied_ev_label": "算定不能",
                    "method": "データ不足",
                })
                continue

            total_ev += seg_ev
            segment_results.append({
                "name": seg.name,
                "implied_ev": round(seg_ev),
                "implied_ev_label": _format_jpy(seg_ev),
                "method": method,
            })

        if total_ev <= 0:
            return {"error": "算定可能なセグメントがなく合計EVが0以下です", "warnings": warnings}

        # 単位補正（DCFValuationToolと同ロジック）
        scale_note = ""
        if p.shares_outstanding > 100_000 and total_ev < p.shares_outstanding:
            logger.warning("SOTP合計EVが発行済株式数より小さいため百万円単位と判定し補正します")
            for sr in segment_results:
                if sr["implied_ev"] is not None:
                    sr["implied_ev"] = round(sr["implied_ev"] * 1_000_000)
                    sr["implied_ev_label"] = _format_jpy(sr["implied_ev"])
            total_ev *= 1_000_000
            scale_note = "※入力された財務数値が百万円単位であったため1,000,000倍に自動補正しました。"

        equity_value = total_ev - p.net_debt
        intrinsic_price = equity_value / p.shares_outstanding

        result = {
            "method": "SOTP法（Sum-of-the-Parts）",
            "segment_results": segment_results,
            "total_ev": round(total_ev),
            "total_ev_label": _format_jpy(total_ev),
            "net_debt": round(p.net_debt),
            "equity_value": round(equity_value),
            "equity_value_label": _format_jpy(equity_value),
            "intrinsic_price_per_share": round(intrinsic_price, 2),
            "ev_composition": (
                f"SOTP合計EV={_format_jpy(total_ev)} - 純有利子負債{_format_jpy(p.net_debt)}"
                f" = 株主価値{_format_jpy(equity_value)}"
            ),
        }
        if warnings:
            result["warnings"] = warnings
        if scale_note:
            result["scale_note"] = scale_note
        return result

# ===== 乖離率・割高割安判定ツール =====

class ValuationComparisonInput(BaseModel):
    current_price: float               # 現在株価（円）
    dcf_intrinsic_price: float         # DCF法による理論株価（円）
    multiples_per_price: float = 0.0   # マルチプル法（PER）による理論株価（円）
    multiples_ev_ebitda_price: float = 0.0  # マルチプル法（EV/EBITDA）による理論株価（円）
    roic: float = 0.0       # FinancialCalcToolのROIC出力（小数, 例: 0.035）。0なら評価スキップ
    base_wacc: float = 0.0  # DCFValuationToolのwacc出力（小数, 例: 0.059）。0なら評価スキップ


class ValuationComparisonTool(BaseTool):
    """
    現在株価と理論株価を比較し、乖離率と割高/割安の判定をPythonで計算する。
    LLMに乖離率の計算や割高/割安の判定を絶対にさせないこと。必ずこのToolを使うこと。

    乖離率 = (現在株価 - 理論株価) / 理論株価 × 100
    - プラス（+）→ 現在株価が理論株価を「上回る」→ 割高
    - マイナス（-）→ 現在株価が理論株価を「下回る」→ 割安
    """
    name: str = "ValuationComparisonTool"
    description: str = (
        "現在株価と各手法の理論株価を受け取り、乖離率（%）と割高/割安の判定をPythonで計算する。\n"
        "乖離率 = (現在株価 - 理論株価) / 理論株価 × 100。\n"
        "プラス=割高、マイナス=割安。LLMは計算・判定を自分で行わず必ずこのToolを使うこと。\n"
        "current_price: 現在株価、dcf_intrinsic_price: DCF理論株価、\n"
        "multiples_per_price: PER法理論株価（0なら省略）、multiples_ev_ebitda_price: EV/EBITDA法理論株価（0なら省略）"
    )
    args_schema: type[BaseModel] = ValuationComparisonInput

    def _run(self, **kwargs) -> dict:
        try:
            p = ValuationComparisonInput(**kwargs)
        except Exception as e:
            return {"error": f"入力パラメータエラー: {e}"}

        def _calc(intrinsic: float) -> dict:
            """乖離率と割高/割安を計算する内部ヘルパー。"""
            if intrinsic <= 0:
                return {"error": "理論株価が0以下のため計算不能"}
            deviation_pct = (p.current_price - intrinsic) / intrinsic * 100
            if deviation_pct > 0:
                judgment = "割高"
                summary = f"現在株価は理論値比 +{deviation_pct:.1f}% 割高"
            elif deviation_pct < 0:
                judgment = "割安"
                summary = f"現在株価は理論値比 {deviation_pct:.1f}% 割安"
            else:
                judgment = "適正"
                summary = "現在株価は理論値と一致（適正水準）"
            return {
                "intrinsic_price": round(intrinsic, 2),
                "current_price": round(p.current_price, 2),
                "deviation_pct": round(deviation_pct, 1),
                "judgment": judgment,
                "summary": summary,
            }

        result = {
            "method": "ValuationComparison",
            "dcf": _calc(p.dcf_intrinsic_price),
        }

        # PER法（任意）
        if p.multiples_per_price > 0:
            result["multiples_per"] = _calc(p.multiples_per_price)

        # EV/EBITDA法（任意）
        if p.multiples_ev_ebitda_price > 0:
            result["multiples_ev_ebitda"] = _calc(p.multiples_ev_ebitda_price)

        # 平均理論株価と総合判定
        prices = [p.dcf_intrinsic_price]
        if p.multiples_per_price > 0:
            prices.append(p.multiples_per_price)
        if p.multiples_ev_ebitda_price > 0:
            prices.append(p.multiples_ev_ebitda_price)
        if len(prices) > 1:
            avg_price = sum(prices) / len(prices)
            result["average"] = _calc(avg_price)
            result["average"]["avg_intrinsic_price"] = round(avg_price, 2)

        return result
