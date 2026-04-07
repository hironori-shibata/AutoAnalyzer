"""
企業価値計算ツール（逆DCF法・PER法・SOTP法）
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
    # 時価総額ディスカウント補正用（PER法）
    peer_market_caps: list[float] = []     # 同業他社の時価総額（円単位, peer_persと同順）
    target_market_cap: float = 0.0         # 対象企業の時価総額（円単位）

    @field_validator('peer_pers', 'peer_ev_ebitdas', 'segment_weights', 'segment_median_pers', 'peer_market_caps', mode='before')
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
        "【時価総額ディスカウント補正（PER法）】peer_market_caps・target_market_capを同時に渡すと、\n"
        "対象企業の時価総額の1/2未満の同業他社のPERを自動割引する（小規模ほど割引）。\n"
        "渡さない場合は peer_pers をそのまま使用する。\n"
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

        # ---- 時価総額ベースのPER割引補正 ----
        # 対象企業の時価総額の1/2未満の同業他社はPremiumが過大になりがちなのでPERを割引する。
        # 割引係数 = (ratio / 0.5) ^ 1  [ratio < 0.5 の場合のみ]
        # ・ratio = 0.50 → 係数 1.00（割引なし）
        # ・ratio = 0.25 → 係数 ≈ 0.76（24%割引）
        # ・ratio = 0.10 → 係数 ≈ 0.50（50%割引）
        # 対象企業より大きい（ratio >= 0.5）場合は増やさずそのまま使用する。
        per_size_discount_note = ""
        working_peer_pers = list(p.peer_pers)
        if (p.peer_market_caps
                and len(p.peer_market_caps) == len(p.peer_pers)
                and p.target_market_cap > 0):
            adjusted_pers = []
            discount_detail_lines = []
            for per, peer_cap in zip(p.peer_pers, p.peer_market_caps):
                ratio = peer_cap / p.target_market_cap
                if ratio >= 0.5:
                    factor = 1.0
                else:
                    factor = (ratio / 0.5) ** 1
                factor=max(factor,0.5) # 最低でも50%割引（50%の係数）までにする。極端に小さい企業がいる場合の過剰補正を防止。
                adj = per * factor
                adjusted_pers.append(adj)
                disc_pct = (1 - factor) * 100
                discount_detail_lines.append(
                    f"  - PER {per:.1f}倍 × 補正係数{factor:.3f}"
                    f"（時価総額比{ratio:.2%}, -{disc_pct:.0f}%割引）→ {adj:.2f}倍"
                )
            working_peer_pers = adjusted_pers
            adj_median = statistics.median(adjusted_pers)
            per_size_discount_note = (
                f"時価総額ディスカウント補正後 PER中央値 = **{adj_median:.2f}倍**\n"
                + "\n".join(discount_detail_lines)
            )
            logger.info(f"PER size-discount: raw median={statistics.median(p.peer_pers):.2f}x → adjusted median={adj_median:.2f}x")

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

        # PER法: セグメント加重PERが使える場合はそちらを優先、なければ補正後中央値にフォールバック
        median_per = statistics.median(working_peer_pers)
        effective_per = segment_weighted_per if segment_weighted_per is not None else median_per

        result = {
            "method": "マルチプル法（PER法＋EV/EBITDA法）",
        }

        # EPS <= 0（赤字企業）の場合はPER法を適用不可
        if p.target_eps <= 0:
            result["per_method"] = {
                "error": "target_eps が0以下のためPER法は適用不可（赤字企業）。PBR法・EV/Revenue法等の代替指標を使用すること。",
                "target_eps": p.target_eps,
                "effective_per_used": round(effective_per, 2),
            }
        else:
            per_price = p.target_eps * effective_per
            result["per_method"] = {
                "raw_median_peer_per": round(statistics.median(p.peer_pers), 2),
                "median_peer_per": round(median_per, 2),
                "effective_per_used": round(effective_per, 2),
                "per_implied_price": round(per_price, 2),
            }
            if per_size_discount_note:
                result["per_method"]["size_discount_note"] = per_size_discount_note
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

        return result


# ===== 逆DCF法（Exit Multiple方式）=====

class ReverseDCFInput(BaseModel):
    current_ev: float               # 現在のEV（時価総額 + 純有利子負債, 円単位）
    ebitda_0: float                 # 現在のEBITDA（円単位, 最新決算ベース）
    exit_multiple: float            # TerminalのEV/EBITDAマルチプル（例: 8.0）
    projection_years: int = 5       # 予測年数（デフォルト5年）
    shares_outstanding: float = 0.0 # 発行済株式数（シナリオテーブルの株価換算用）
    net_debt: float = 0.0           # 純有利子負債（シナリオテーブルの株価換算用, 円単位）
    # WACC: 直接指定 or CAPMコンポーネントから自動計算
    wacc: float = 0.0               # 0なら以下のCAPMコンポーネントから自動計算
    risk_free_rate: float = DCF_DEFAULTS["risk_free_rate"]
    equity_risk_premium: float = DCF_DEFAULTS["equity_risk_premium"]
    beta: float = DCF_DEFAULTS["beta"]
    debt_cost: float = DCF_DEFAULTS["debt_cost"]
    # 負債比率: interest_bearing_debt > 0 かつ target_market_cap > 0 の場合は
    # D/(D+E) = interest_bearing_debt / (interest_bearing_debt + target_market_cap) で自動計算
    # 両者が未提供の場合のみデフォルト値（0.3）を使用する
    debt_ratio: float = DCF_DEFAULTS["debt_ratio"]
    interest_bearing_debt: float = 0.0  # 有利子負債合計（円単位）。WACC負債比率の自動計算用
    tax_rate: float = DCF_DEFAULTS["tax_rate"]
    # 比較用の期待成長率（Agent4の歴史的CAGRなど）
    expected_growth_rate: float = 0.0  # 0なら比較コメントなし
    # 時価総額ベースのExitMultiple補正用（オプション）
    # 対象企業の1/2未満の時価総額を持つ同業他社のMultipleを自動割引する
    peer_ev_ebitdas: list[float] = []   # 同業他社のEV/EBITDA一覧
    peer_market_caps: list[float] = []  # 同業他社の時価総額（円単位, peer_ev_ebitdasと同順）
    target_market_cap: float = 0.0      # 対象企業の時価総額（円単位）

    @field_validator('peer_ev_ebitdas', 'peer_market_caps', mode='before')
    @classmethod
    def _parse_float_list(cls, v):
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


class ReverseDCFTool(BaseTool):
    """
    逆DCF法（Exit Multiple方式）で市場が現在価格に織り込む成長率を逆算する。

    EV = Σ[EBITDA_0*(1+g)^t / (1+r)^t] + [EBITDA_0*(1+g)^N * Multiple / (1+r)^N]
    上式を満たす g を二分法で求め、「市場が織り込む成長前提」として可視化する。
    """
    name: str = "ReverseDCFTool"
    description: str = (
        "逆DCF法（Exit Multiple方式）で市場が織り込むEBITDA成長率を逆算する。\n"
        "current_ev: 現在のEV（時価総額+純有利子負債, 円単位）\n"
        "ebitda_0: 現在のEBITDA（円単位）\n"
        "exit_multiple: 競合データが一切取得できない場合のフォールバック値（通常はpeer_ev_ebitdas渡しで自動計算）。\n"
        "⚠️【推奨】peer_ev_ebitdas・peer_market_caps・target_market_capを渡すと時価総額ディスカウント補正後の\n"
        "中央値を自動計算してExitMultipleとして使用する（その場合exit_multipleは無視される）。\n"
        "【WACCパラメータ（wacc=0のとき以下でCAPM自動計算）】\n"
        "beta: 業種別β目安 — 公益/食品: 0.5〜0.7 / 化学/製薬: 0.8〜1.0 / 自動車/重工: 0.9〜1.2 / 半導体/IT: 1.2〜1.8。\n"
        "  省略時はデフォルト1.1（業種不明フォールバック）。\n"
        "interest_bearing_debt: 有利子負債合計（円単位）。渡すと D/(D+E)=有利子負債/(有利子負債+時価総額) で\n"
        "  負債比率を市場価値ベースで自動計算する。省略するとデフォルト30%が使われ精度が低下する。\n"
        "  ⚠️ target_market_capと必ずセットで渡すこと。\n"
        "debt_cost: 省略時は target_market_cap の規模に応じて自動設定される（負債コスト規模連動）。\n"
        "  超大型(≥5兆円): 0.8% / 大型(1〜5兆円): 1.0% / 中型(3000億〜1兆円): 1.5% / 小型(<3000億円): 2.0%\n"
        "wacc: WACCを直接指定（0なら上記コンポーネントから自動計算）\n"
        "expected_growth_rate: 比較用の期待成長率（Agent4のCAGR等, 0なら省略）\n"
        "shares_outstanding・net_debt: シナリオテーブルの株価換算用（省略可）\n"
        "【時価総額ディスカウント補正】peer_ev_ebitdas・peer_market_caps・target_market_capを同時に渡すと、\n"
        "対象企業の時価総額の1/2未満の同業他社のMultipleを自動割引する（小規模ほど大きく割引）。\n"
        "渡さない場合は exit_multiple をそのまま使用する。\n"
        "⚠️ 金額パラメータ（current_ev, ebitda_0, net_debt, interest_bearing_debt, peer_market_caps, target_market_cap）はすべて【実際の円単位】で入力すること。"
    )
    args_schema: type[BaseModel] = ReverseDCFInput

    def _run(self, **kwargs) -> dict:
        try:
            p = ReverseDCFInput(**kwargs)
        except Exception as e:
            return {"error": f"入力パラメータエラー: {e}"}

        if p.current_ev <= 0:
            return {"error": "current_ev が0以下です"}
        if p.ebitda_0 <= 0:
            return {"error": "ebitda_0 が0以下です（EBITDAが負または0の企業には逆DCFは適用できません）"}
        if p.exit_multiple <= 0:
            return {"error": "exit_multiple が0以下です"}

        # WACC 決定
        if p.wacc > 0:
            wacc = p.wacc
            wacc_note = f"WACC={wacc:.2%}（直接指定）"
        else:
            # [P5] 負債比率: target_market_cap > 0 であれば市場価値ベースで自動計算
            # 無借金企業 (interest_bearing_debt=0) でも D/(D+E)=0% として正しく算出する
            if p.target_market_cap > 0:
                debt_ratio = p.interest_bearing_debt / (p.interest_bearing_debt + p.target_market_cap)
                if p.interest_bearing_debt > 0:
                    debt_ratio_note = (
                        f"D/(D+E)={debt_ratio:.1%}"
                        f"（有利子負債{p.interest_bearing_debt/1e8:.0f}億円"
                        f"÷(同+時価総額{p.target_market_cap/1e8:.0f}億円）・市場価値ベース）"
                    )
                else:
                    debt_ratio_note = "D/(D+E)=0%（無借金企業・市場価値ベース）"
            else:
                debt_ratio = p.debt_ratio
                debt_ratio_note = f"D/(D+E)={debt_ratio:.0%}（⚠️ デフォルト値・target_market_cap未提供）"

            # [P4] 負債コスト: デフォルト値使用かつ時価総額が提供された場合は規模連動で自動設定
            _using_default_debt_cost = abs(p.debt_cost - DCF_DEFAULTS["debt_cost"]) < 1e-9
            if _using_default_debt_cost and p.target_market_cap > 0:
                if p.target_market_cap >= 5_000_000_000_000:      # 5兆円以上: 超大型
                    debt_cost = 0.008
                    debt_cost_tier = "超大型株(≥5兆円): 0.8%"
                elif p.target_market_cap >= 1_000_000_000_000:    # 1〜5兆円: 大型
                    debt_cost = 0.010
                    debt_cost_tier = "大型株(1〜5兆円): 1.0%"
                elif p.target_market_cap >= 300_000_000_000:      # 3000億〜1兆円: 中型
                    debt_cost = 0.015
                    debt_cost_tier = "中型株(3000億〜1兆円): 1.5%"
                else:                                              # 3000億円未満: 小型
                    debt_cost = 0.020
                    debt_cost_tier = "小型株(<3000億円): 2.0%"
            else:
                debt_cost = p.debt_cost
                debt_cost_tier = None

            re_val = p.risk_free_rate + p.beta * p.equity_risk_premium
            wacc = (1 - debt_ratio) * re_val + debt_ratio * debt_cost * (1 - p.tax_rate)

            # デフォルト値使用の警告フラグ
            _default_warnings = []
            if abs(p.beta - DCF_DEFAULTS["beta"]) < 1e-9:
                _default_warnings.append("β=デフォルト1.1（業種別推定推奨）")
            if p.target_market_cap == 0:
                _default_warnings.append("D/(D+E)=デフォルト30%（target_market_cap未提供）")

            wacc_note = (
                f"WACC={wacc:.2%}（CAPM自動計算: Rf={p.risk_free_rate:.2%}, "
                f"ERP={p.equity_risk_premium:.2%}, β={p.beta}, "
                f"Rd={debt_cost:.2%}" + (f"[{debt_cost_tier}]" if debt_cost_tier else "") +
                f", {debt_ratio_note}）"
            )
            if _default_warnings:
                wacc_note += f" ⚠️ デフォルト値使用: {', '.join(_default_warnings)}"

        N = p.projection_years
        M = p.exit_multiple

        # ---- 時価総額ベースのExitMultiple補正 ----
        # 対象企業の時価総額の1/2未満の同業他社は割高評価になりがちなのでMultipleを割引する。
        # 割引係数 = (ratio / 0.5) ^ 1  [ratio < 0.5 の場合のみ]
        # ・ratio = 0.50 → 係数 1.00（割引なし）
        # ・ratio = 0.25 → 係数 ≈ 0.76（24%割引）
        # ・ratio = 0.10 → 係数 ≈ 0.50（50%割引）
        # ・ratio = 0.05 → 係数 ≈ 0.40（60%割引）
        # 対象企業より大きい（ratio >= 0.5）場合は増やさずそのまま使用する。
        size_discount_note = ""
        if (p.peer_ev_ebitdas
                and p.peer_market_caps
                and len(p.peer_ev_ebitdas) == len(p.peer_market_caps)
                and p.target_market_cap > 0):
            adjusted_multiples = []
            discount_detail_lines = []
            for mult, peer_cap in zip(p.peer_ev_ebitdas, p.peer_market_caps):
                ratio = peer_cap / p.target_market_cap
                if ratio >= 0.5:
                    factor = 1.0
                else:
                    factor = (ratio / 0.5) ** 1
                factor=max(factor,0.5)
                adj = mult * factor
                adjusted_multiples.append(adj)
                disc_pct = (1 - factor) * 100
                discount_detail_lines.append(
                    f"  - EV/EBITDA {mult:.1f}x × 補正係数{factor:.3f}"
                    f"（時価総額比{ratio:.2%}, -{disc_pct:.0f}%割引）→ {adj:.2f}x"
                )
            M = statistics.median(adjusted_multiples)
            size_discount_note = (
                f"時価総額ディスカウント補正後 ExitMultiple（中央値）= **{M:.2f}x**\n"
                + "\n".join(discount_detail_lines)
            )
            logger.info(f"ExitMultiple size-discount: base={p.exit_multiple}x → adjusted median={M:.2f}x")

        # 単位補正チェック
        scale_note = ""
        current_ev = p.current_ev
        ebitda_0 = p.ebitda_0
        net_debt = p.net_debt

        if ebitda_0 > 0 and current_ev / ebitda_0 < 1.0:
            logger.warning("current_ev/ebitda_0 < 1.0: 百万円単位入力の疑いがあるため1,000,000倍に自動補正します")
            current_ev *= 1_000_000
            ebitda_0 *= 1_000_000
            net_debt *= 1_000_000
            scale_note = "※入力が百万円単位と判定し1,000,000倍に自動補正しました。"

        def _calc_ev(g: float, _e=None, _w=None, _N=None, _M=None) -> float:
            e = _e if _e is not None else ebitda_0
            w = _w if _w is not None else wacc
            n = _N if _N is not None else N
            m = _M if _M is not None else M
            ebitdas = [e * (1 + g) ** t for t in range(1, n + 1)]
            pv_ebitda = sum(ev / (1 + w) ** t for t, ev in enumerate(ebitdas, 1))
            tv = ebitdas[-1] * m
            pv_tv = tv / (1 + w) ** n
            return pv_ebitda + pv_tv

        # ---- 二分法（Bisection）で implied_g を求める ----
        g_lo, g_hi = -0.50, 1.00
        ev_lo = _calc_ev(g_lo)
        ev_hi = _calc_ev(g_hi)

        implied_g = None
        if ev_lo <= current_ev <= ev_hi:
            for _ in range(200):
                g_mid = (g_lo + g_hi) / 2
                ev_mid = _calc_ev(g_mid)
                if abs(ev_mid - current_ev) / current_ev < 1e-8:
                    implied_g = g_mid
                    break
                if ev_mid < current_ev:
                    g_lo = g_mid
                else:
                    g_hi = g_mid
            if implied_g is None:
                implied_g = (g_lo + g_hi) / 2

        if implied_g is None:
            return {
                "error": (
                    "implied_g の探索範囲（-50%〜+100%）内で収束しませんでした。"
                    f"（EV={_format_jpy(current_ev)}, EBITDA={_format_jpy(ebitda_0)}, "
                    f"EV/EBITDA_0={current_ev/ebitda_0:.1f}x）"
                )
            }

        # ---- シナリオテーブル（各成長率での implied EV・株価）----
        scenario_gs = [-0.05, 0.0, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20]
        tol = 0.005
        if not any(abs(implied_g - g) < tol for g in scenario_gs):
            scenario_gs.append(implied_g)
        scenario_gs.sort()

        scenario_rows = []
        for g in scenario_gs:
            ev_g = _calc_ev(g)
            eq_g = ev_g - net_debt
            price_g = (eq_g / p.shares_outstanding) if p.shares_outstanding > 0 else None
            is_implied = abs(g - implied_g) < tol
            marker = " ◀ 市場織込" if is_implied else ""
            price_str = (f"{round(price_g):,}円" if price_g is not None else "—")
            scenario_rows.append(
                f"| {g*100:+.1f}% | {_format_jpy(ev_g)} | {price_str}{marker} |"
            )

        price_col = "株価（目安）" if p.shares_outstanding > 0 else "株価（—）"
        scenario_md = (
            f"| EBITDA成長率(g) | implied EV | {price_col} |\n"
            f"|---|---|---|\n"
            + "\n".join(scenario_rows)
        )

        # ---- 感応度テーブル（WACC × ExitMultiple → implied_g）----
        wacc_deltas = [-0.01, -0.005, 0.0, +0.005, +0.01]
        # 実際のExitMultiple Mを中心に±2行のコンテキストを表示する
        _std_ms = [4.0, 6.0, 8.0, 10.0, 12.0, 14.0, 16.0, 18.0, 20.0]
        _pool = sorted(set(_std_ms + [float(M)]))
        _mi = _pool.index(float(M))
        _lo = max(0, _mi - 2)
        _hi = _lo + 5
        if _hi > len(_pool):
            _hi = len(_pool)
            _lo = max(0, _hi - 5)
        exit_multiples = _pool[_lo:_hi]

        sens_rows = []
        wacc_hdrs = [f"WACC {(wacc + d)*100:.2f}%" for d in wacc_deltas]
        for mult in exit_multiples:
            row_cells = []
            for wd in wacc_deltas:
                w = wacc + wd
                if w <= 0:
                    row_cells.append("N/A")
                    continue
                gl, gh = -0.50, 1.00
                evl, evh = _calc_ev(gl, _w=w, _M=mult), _calc_ev(gh, _w=w, _M=mult)
                if not (evl <= current_ev <= evh):
                    row_cells.append("範囲外")
                    continue
                for _ in range(150):
                    gm = (gl + gh) / 2
                    evm = _calc_ev(gm, _w=w, _M=mult)
                    if abs(evm - current_ev) / current_ev < 1e-7:
                        break
                    if evm < current_ev:
                        gl = gm
                    else:
                        gh = gm
                row_cells.append(f"{((gl + gh) / 2)*100:+.1f}%")
            sens_rows.append(f"| {mult:.0f}x | " + " | ".join(row_cells) + " |")

        sens_md = (
            "| ExitMultiple＼WACC | " + " | ".join(wacc_hdrs) + " |\n"
            "|---|" + "---|" * len(wacc_deltas) + "\n"
            + "\n".join(sens_rows)
        )

        # ---- 解釈コメント ----
        interpretation_lines = [
            f"現在EVは {_format_jpy(current_ev)}。",
            f"市場が織り込むEBITDA成長率（implied g）= **{implied_g*100:+.2f}%/年**（{N}年間, ExitMultiple={M:.1f}x）。",
        ]
        if p.expected_growth_rate != 0.0:
            diff = implied_g - p.expected_growth_rate
            if diff > 0.02:
                verdict = "市場は期待成長率を上回る成長を織り込んでいる → **割高示唆**"
            elif diff < -0.02:
                verdict = "市場は期待成長率を下回る成長しか織り込んでいない → **割安示唆**"
            else:
                verdict = "市場の織り込み成長率は期待成長率とほぼ一致 → **概ね適正**"
            interpretation_lines.append(
                f"期待成長率（比較値）= {p.expected_growth_rate*100:+.1f}%/年 → "
                f"乖離 = {diff*100:+.1f}pt → {verdict}"
            )

        result_rdcf = {
            "method": "逆DCF法（Exit Multiple方式）",
            "wacc_note": wacc_note,
            "wacc": round(wacc, 4),
            "exit_multiple": M,
            "projection_years": N,
            "current_ev": round(current_ev),
            "current_ev_label": _format_jpy(current_ev),
            "ebitda_0": round(ebitda_0),
            "ebitda_0_label": _format_jpy(ebitda_0),
            "current_ev_ebitda_ratio": round(current_ev / ebitda_0, 1),
            "implied_growth_rate": round(implied_g, 4),
            "implied_growth_rate_pct": f"{implied_g*100:+.2f}%",
            "scenario_table_markdown": scenario_md,
            "sensitivity_table_markdown": sens_md,
            "interpretation": " / ".join(interpretation_lines),
        }
        if scale_note:
            result_rdcf["scale_note"] = scale_note
        if size_discount_note:
            result_rdcf["size_discount_note"] = size_discount_note
        return result_rdcf


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
    dcf_intrinsic_price: float = 0.0   # DCF法による理論株価（円）。0なら省略（逆DCF移行後は不要）
    multiples_per_price: float = 0.0   # マルチプル法（PER）による理論株価（円）
    multiples_ev_ebitda_price: float = 0.0  # マルチプル法（EV/EBITDA）による理論株価（円）
    roic: float = 0.0       # FinancialCalcToolのROIC出力（小数, 例: 0.035）。0なら評価スキップ
    base_wacc: float = 0.0  # WACCの値（小数, 例: 0.059）。0なら評価スキップ


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

        result: dict = {"method": "ValuationComparison"}

        # DCF法（任意 - 逆DCF移行後は省略可）
        if p.dcf_intrinsic_price > 0:
            result["dcf"] = _calc(p.dcf_intrinsic_price)

        # PER法（任意）
        if p.multiples_per_price > 0:
            result["multiples_per"] = _calc(p.multiples_per_price)

        # EV/EBITDA法（任意）
        if p.multiples_ev_ebitda_price > 0:
            result["multiples_ev_ebitda"] = _calc(p.multiples_ev_ebitda_price)

        # 平均理論株価と総合判定
        prices = []
        if p.dcf_intrinsic_price > 0:
            prices.append(p.dcf_intrinsic_price)
        if p.multiples_per_price > 0:
            prices.append(p.multiples_per_price)
        if p.multiples_ev_ebitda_price > 0:
            prices.append(p.multiples_ev_ebitda_price)
        if len(prices) > 1:
            avg_price = sum(prices) / len(prices)
            result["average"] = _calc(avg_price)
            result["average"]["avg_intrinsic_price"] = round(avg_price, 2)

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
