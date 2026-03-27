"""
企業価値計算ツール (DCF法・PER法)
Agent6 (統括マネージャー) が使用する。LLMには計算をさせない。
"""
import statistics
from crewai.tools import BaseTool
from pydantic import BaseModel
from loguru import logger

from src.config import DCF_DEFAULTS


# ===== DCF法 =====

class DCFInput(BaseModel):
    free_cash_flows: list[float]       # 過去のFCF（直近3〜5年・古い順）
    revenue_cagr: float                # 売上CAGR（Agent4から）
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


# ===== マルチプル法 =====

class MultiplesInput(BaseModel):
    target_eps: float                      # 対象企業EPS（Agent3から）
    peer_pers: list[float]                 # 同業他社のPER一覧（Agent2から）


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

        # WACC計算 (CAPM)
        re = p.risk_free_rate + p.beta * p.equity_risk_premium
        wacc = (1 - p.debt_ratio) * re + p.debt_ratio * p.debt_cost * (1 - p.tax_rate)

        if wacc <= p.terminal_growth_rate:
            logger.warning("WACC <= 永久成長率。継続価値計算が不安定になるため調整します")
            wacc = p.terminal_growth_rate + 0.01

        # 直近FCFをベースに将来FCFを予測
        base_fcf = p.free_cash_flows[-1]
        projected_fcfs = [
            base_fcf * (1 + p.revenue_cagr) ** t
            for t in range(1, p.projection_years + 1)
        ]

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
        note = ""
        if p.shares_outstanding and p.shares_outstanding > 100_000:
            if enterprise_value < p.shares_outstanding:
                logger.warning("DCF企業価値が発行済株式数より小さいため、入力値が『百万円単位』と判定し、1,000,000倍に自動補正します。")
                if intrinsic_price is not None:
                    intrinsic_price *= 1_000_000
                enterprise_value *= 1_000_000
                equity_value *= 1_000_000
                pv_fcfs *= 1_000_000
                tv *= 1_000_000
                pv_tv *= 1_000_000
                projected_fcfs = [f * 1_000_000 for f in projected_fcfs]
                note = "※入力された財務数値が百万円単位であったため、計算過程で自動的に1,000,000倍（1円単位）に補正して算定しました。"

        if tv_ratio > 0.9:
            note += ("\n※警告: 企業価値の90%以上が継続価値（将来の不確実な予測）で占められています。算定結果の取り扱いには注意してください。" if not note else 
                     "\n※追加警告: 企業価値の90%以上が継続価値で占められており、予測の不確実性が非常に高いです。")

        res = {
            "method": "DCF法",
            "wacc": round(wacc, 4),
            "projected_fcfs": [round(f) for f in projected_fcfs],
            "pv_fcfs": round(pv_fcfs),
            "terminal_value": round(tv),
            "pv_terminal_value": round(pv_tv),
            "tv_ratio": round(tv_ratio, 4),
            "enterprise_value": round(enterprise_value),
            "equity_value": round(equity_value),
            "intrinsic_price_per_share": round(intrinsic_price, 2) if intrinsic_price else None,
        }
        if note:
            res["note"] = note
        return res


class MultiplesValuationTool(BaseTool):
    """
    マルチプル法（PER法・EV/EBITDA法）で企業価値と理論株価を計算する。
    """
    name: str = "MultiplesValuationTool"
    description: str = (
        "マルチプル法（PER法）で理論株価をPythonで計算する。Agent6が使用する。\n"
        "target_eps: 対象企業の予想EPS（円/株）、peer_pers: 競合他社のPER一覧（倍）を渡すこと。"
    )
    args_schema: type[BaseModel] = MultiplesInput

    def _run(self, **kwargs) -> dict:
        try:
            p = MultiplesInput(**kwargs)
        except Exception as e:
            return {"error": f"入力パラメータエラー: {e}"}

        if not p.peer_pers:
            return {"error": "peer_pers が空です。PER法による算定ができません。"}

        # PER法
        median_per = statistics.median(p.peer_pers)
        per_price = p.target_eps * median_per

        return {
            "method": "マルチプル法（PER法）",
            "median_peer_per": round(median_per, 2),
            "per_implied_price": round(per_price, 2),
        }
