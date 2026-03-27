"""
財務指標計算ツール・トレンド分析ツール
LLMに数値計算をさせず、すべてPythonで計算する（設計書の最重要ルール）。
"""
import numpy as np
from crewai.tools import BaseTool
from pydantic import BaseModel


# ===== FinancialCalcTool =====

class FinancialCalcInput(BaseModel):
    net_income: float            # 当期純利益
    total_assets: float          # 総資産
    equity: float                # 自己資本（純資産）
    shares_outstanding: float    # 発行済株式数
    revenue: float               # 売上高
    operating_income: float      # 営業利益
    current_assets: float        # 流動資産
    current_liabilities: float   # 流動負債
    interest_bearing_debt: float # 有利子負債
    inventory: float             # 棚卸資産
    receivables: float           # 売上債権
    payables: float              # 仕入債務
    cogs: float                  # 売上原価
    operating_cf: float          # 営業キャッシュフロー
    capex: float                 # 設備投資額（支出として絶対値で渡す）


class FinancialCalcTool(BaseTool):
    """
    決算短信から抽出した財務数値を受け取り、
    ROA/ROE/EPS/営業利益率/自己資本比率/流動比率/D/E比率/総資産回転率/CCC/FCF
    を計算して返す。LLMは計算を行わずこのToolを使うこと。
    """
    name: str = "FinancialCalcTool"
    description: str = (
        "決算短信から抽出した財務数値（当期純利益・総資産・自己資本・売上高等）を受け取り、"
        "ROA/ROE/EPS/営業利益率/自己資本比率/流動比率/D‑Eレシオ/資産回転率/CCC/FCF をPythonで計算する。"
        "LLMは絶対に計算を行わずこのToolを使うこと。"
    )
    args_schema: type[BaseModel] = FinancialCalcInput

    def _run(
        self,
        net_income: float,
        total_assets: float,
        equity: float,
        shares_outstanding: float,
        revenue: float,
        operating_income: float,
        current_assets: float,
        current_liabilities: float,
        interest_bearing_debt: float,
        inventory: float,
        receivables: float,
        payables: float,
        cogs: float,
        operating_cf: float,
        capex: float,
    ) -> dict:
        d = FinancialCalcInput(
            net_income=net_income,
            total_assets=total_assets,
            equity=equity,
            shares_outstanding=shares_outstanding,
            revenue=revenue,
            operating_income=operating_income,
            current_assets=current_assets,
            current_liabilities=current_liabilities,
            interest_bearing_debt=interest_bearing_debt,
            inventory=inventory,
            receivables=receivables,
            payables=payables,
            cogs=cogs,
            operating_cf=operating_cf,
            capex=capex,
        )

        # CCC計算
        inv_days = (d.inventory / d.cogs * 365) if d.cogs else 0
        rec_days = (d.receivables / d.revenue * 365) if d.revenue else 0
        pay_days = (d.payables / d.cogs * 365) if d.cogs else 0
        ccc = inv_days + rec_days - pay_days

        return {
            "ROA": round(d.net_income / d.total_assets, 4) if d.total_assets else None,
            "ROE": round(d.net_income / d.equity, 4) if d.equity else None,
            "EPS": round(d.net_income / d.shares_outstanding, 2) if d.shares_outstanding else None,
            "operating_margin": round(d.operating_income / d.revenue, 4) if d.revenue else None,
            "equity_ratio": round(d.equity / d.total_assets, 4) if d.total_assets else None,
            "current_ratio": round(d.current_assets / d.current_liabilities, 4) if d.current_liabilities else None,
            "de_ratio": round(d.interest_bearing_debt / d.equity, 4) if d.equity else None,
            "asset_turnover": round(d.revenue / d.total_assets, 4) if d.total_assets else None,
            "ccc_days": round(ccc, 2),
            # デュポン分解の3要素
            "profit_margin": round(d.net_income / d.revenue, 4) if d.revenue else None,
            "financial_leverage": round(d.total_assets / d.equity, 4) if d.equity else None,
            # FCF (営業CF - 設備投資)
            "fcf": round(d.operating_cf - d.capex, 2),
        }


# ===== TrendAnalysisTool =====

class TrendAnalysisInput(BaseModel):
    values: list[float]   # 時系列データ（古い順）
    years: list[int]      # 対応する年度リスト


class TrendAnalysisTool(BaseTool):
    """
    時系列の数値リストから CAGR・トレンド方向・直近変化率をPythonで計算する。
    Agent4（業績）とAgent5（需給）が使用する。LLMは計算せずこのToolを使うこと。
    """
    name: str = "TrendAnalysisTool"
    description: str = (
        "時系列の数値リスト（古い順）からCAGR・トレンド方向（改善/悪化/横ばい）・直近3年変化率をPythonで計算する。"
        "LLMはCAGRや変化率を自分で計算せずこのToolを使うこと。"
        "values: [float], years: [int] で渡すこと。"
    )
    args_schema: type[BaseModel] = TrendAnalysisInput

    def _run(self, values: list, years: list) -> dict:
        if len(values) < 2:
            return {"error": "データが2件以上必要です"}

        n = len(values) - 1
        
        # CAGRの計算（起点または終点が0以下だと数学的に定義できないため None とする）
        if values[0] <= 0 or values[-1] <= 0:
            cagr = None
        else:
            cagr = ((values[-1] / values[0]) ** (1 / n)) - 1

        x = np.arange(len(values))
        slope = float(np.polyfit(x, values, 1)[0])

        # 直近3年変化率（ゼロ割防止、かつ基準値がマイナスの場合の正しい％算出のため abs(old) で割る）
        recent_change = None
        if len(values) >= 4 and values[-4] != 0:
            recent_change = (values[-1] - values[-4]) / abs(values[-4])

        return {
            "latest_value": values[-1],
            "oldest_value": values[0],
            "cagr": round(cagr, 4) if cagr is not None else None,
            "trend": "改善" if slope > 0 else ("悪化" if slope < 0 else "横ばい"),
            "recent_3yr_change_rate": round(recent_change, 4) if recent_change is not None else None,
            "data_points": len(values),
            "years": years,
        }
