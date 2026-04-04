"""
財務指標計算ツール・トレンド分析ツール
LLMに数値計算をさせず、すべてPythonで計算する（設計書の最重要ルール）。
"""
import json
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
    depreciation: float = 0.0   # 減価償却費（任意: EBITDAおよびROIC計算に使用）
    tax_rate: float = 0.30      # 実効税率（ROIC計算に使用、デフォルト30%）


class FinancialCalcTool(BaseTool):
    """
    決算短信から抽出した財務数値を受け取り、
    ROA/ROE/EPS/営業利益率/自己資本比率/流動比率/D/E比率/総資産回転率/CCC/FCF/EBITDA/ROIC
    を計算して返す。LLMは計算を行わずこのToolを使うこと。
    """
    name: str = "FinancialCalcTool"
    description: str = (
        "決算短信から抽出した財務数値（当期純利益・総資産・自己資本・売上高等）を受け取り、"
        "ROA/ROE/EPS/営業利益率/自己資本比率/流動比率/D‑Eレシオ/資産回転率/CCC/FCF/EBITDA/ROIC をPythonで計算する。"
        "減価償却費(depreciation)を渡すとEBITDAとROICも計算される。"
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
        depreciation: float = 0.0,
        tax_rate: float = 0.30,
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
            depreciation=depreciation,
            tax_rate=tax_rate,
        )

        # CCC計算
        inv_days = (d.inventory / d.cogs * 365) if d.cogs else 0
        rec_days = (d.receivables / d.revenue * 365) if d.revenue else 0
        pay_days = (d.payables / d.cogs * 365) if d.cogs else 0
        ccc = inv_days + rec_days - pay_days

        # EBITDA（減価償却費が渡された場合のみ有効）
        ebitda = d.operating_income + d.depreciation if d.depreciation > 0 else None
        ebitda_margin = round(ebitda / d.revenue, 4) if (ebitda and d.revenue) else None

        # ROIC = NOPAT / 投下資本（有利子負債 + 自己資本）
        # 過剰資本・資本配分効率の評価に使用
        nopat = d.operating_income * (1 - d.tax_rate)
        invested_capital = d.interest_bearing_debt + d.equity
        roic = round(nopat / invested_capital, 4) if invested_capital else None

        result = {
            "ROA": round(d.net_income / d.total_assets, 4) if d.total_assets else None,
            "ROE": round(d.net_income / d.equity, 4) if d.equity else None,
            "ROIC": roic,
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
        if ebitda is not None:
            result["ebitda"] = round(ebitda, 2)
            result["ebitda_margin"] = ebitda_margin
        return result


# ===== TrendAnalysisTool =====

class TrendAnalysisInput(BaseModel):
    values: list[float | None]   # 時系列データ（古い順）。null は自動除去される
    years: list[int]             # 対応する年度リスト


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
        # null/None を含むペアを除去する
        filtered = [(v, y) for v, y in zip(values, years) if v is not None]
        if len(filtered) < 2:
            return {"error": "有効なデータ（null以外）が2件以上必要です"}
        values, years = [v for v, _ in filtered], [y for _, y in filtered]

        n = len(values) - 1
        
        # CAGRの計算（起点または終点が0以下だと数学的に定義できないため None とする）
        if values[0] <= 0 or values[-1] <= 0:
            cagr = None
        else:
            cagr = ((values[-1] / values[0]) ** (1 / n)) - 1

        x = np.arange(len(values))
        slope = float(np.polyfit(x, values, 1)[0])

        # 直近3年・5年・7年変化率（ゼロ割防止、かつ基準値がマイナスの場合の正しい％算出のため abs(old) で割る）
        recent_3yr = None
        if len(values) >= 4 and values[-4] != 0:
            recent_3yr = (values[-1] - values[-4]) / abs(values[-4])

        recent_5yr = None
        if len(values) >= 6 and values[-6] != 0:
            recent_5yr = (values[-1] - values[-6]) / abs(values[-6])

        recent_7yr = None
        if len(values) >= 8 and values[-8] != 0:
            recent_7yr = (values[-1] - values[-8]) / abs(values[-8])

        return {
            "latest_value": values[-1],
            "oldest_value": values[0],
            "cagr": round(cagr, 4) if cagr is not None else None,
            "trend": "改善" if slope > 0 else ("悪化" if slope < 0 else "横ばい"),
            "recent_3yr_change_rate": round(recent_3yr, 4) if recent_3yr is not None else None,
            "recent_5yr_change_rate": round(recent_5yr, 4) if recent_5yr is not None else None,
            "recent_7yr_change_rate": round(recent_7yr, 4) if recent_7yr is not None else None,
            "data_points": len(values),
            "years": years,
        }


# ===== IRBankTrendBatchTool =====

def _trend_stats(values: list, years: list) -> dict:
    """TrendAnalysisToolと同ロジックの内部ヘルパー。Noneを除去してCAGR・トレンドを返す。"""
    filtered = [(v, y) for v, y in zip(values, years) if v is not None]
    if len(filtered) < 2:
        return {"error": "有効データ2件未満"}
    vals = [v for v, _ in filtered]
    yrs = [y for _, y in filtered]
    n = len(vals) - 1
    cagr = None
    if vals[0] > 0 and vals[-1] > 0:
        cagr = round(((vals[-1] / vals[0]) ** (1 / n)) - 1, 4)
    slope = float(np.polyfit(np.arange(len(vals)), vals, 1)[0])
    recent_3yr = None
    if len(vals) >= 4 and vals[-4] != 0:
        recent_3yr = round((vals[-1] - vals[-4]) / abs(vals[-4]), 4)
    return {
        "latest": vals[-1],
        "oldest": vals[0],
        "cagr": cagr,
        "trend": "改善" if slope > 0 else ("悪化" if slope < 0 else "横ばい"),
        "recent_3yr_change_rate": recent_3yr,
        "years": yrs,
        "data_points": len(vals),
    }


# 各セクションから抽出する指標定義
_BATCH_METRICS = {
    "pl": ["revenue", "operating_profit", "net_income", "eps", "roe", "roa", "operating_margin"],
    "bs": ["equity_ratio"],
    "cf": ["operating_cf", "investing_cf", "free_cf"],
    "dividend": ["dividend_per_share", "payout_ratio"],
}


class IRBankTrendBatchInput(BaseModel):
    edinet_code: str  # EdinetCode（E0XXXXX形式）


class IRBankTrendBatchTool(BaseTool):
    """
    EdinetCodeを受け取り、IR Bankから財務データを内部取得したうえで
    全主要指標（売上・利益・ROE/ROA・CF・配当等）のトレンド分析を一括実行する。

    IRBankFinancialTableTool の呼び出しとトレンド計算を1回のツール呼び出しで完結させる。
    LLMが大きなJSONを引数として渡す必要がないため、長期間データでも正確に動作する。

    返却値:
      raw    : IRBankFinancialTableToolと同等の生データ（pl/bs/cf/dividend）。推移テーブル表示に使用。
      trends : 指標名 → {cagr, trend, recent_3yr_change_rate, latest, oldest, years}。

    セグメントデータはこのツールでは取得できないため、
    IRBankScraperTool(section='segment') + TrendAnalysisTool を使用すること。
    """
    name: str = "IRBankTrendBatchTool"
    description: str = (
        "EdinetCodeを指定するだけで、IR Bankから財務データを取得し、"
        "売上・営業利益・純利益・EPS・ROE・ROA・営業利益率・自己資本比率・"
        "営業CF・投資CF・FCF・一株配当・配当性向の全トレンドをPythonで一括計算して返す。"
        "返却値の raw セクションに生データ（推移テーブル表示用）、"
        "trends セクションに各指標のCAGR・トレンド方向・直近変化率が含まれる。"
        "IRBankFinancialTableTool を事前に呼ぶ必要はない。"
        "edinet_code: EdinetCode（E0XXXXX形式）を指定すること。"
    )
    args_schema: type[BaseModel] = IRBankTrendBatchInput

    def _run(self, edinet_code: str) -> str:
        # 内部でIRBankFinancialTableToolを呼び出す（LLMに大きなJSONを渡させない）
        from src.tools.irbank_scraper import IRBankFinancialTableTool
        raw_json = IRBankFinancialTableTool()._run(edinet_code=edinet_code)

        try:
            data = json.loads(raw_json)
        except Exception as e:
            return json.dumps({"error": f"IRBankデータ取得・パース失敗: {e}"}, ensure_ascii=False)

        if "error" in data:
            return json.dumps(data, ensure_ascii=False)

        trends: dict = {}
        for section, fields in _BATCH_METRICS.items():
            rows = data.get(section, [])
            if not rows:
                continue
            years = []
            for r in rows:
                try:
                    years.append(int(str(r.get("year", "0"))[:4]))
                except ValueError:
                    years.append(0)
            for field in fields:
                values = [r.get(field) for r in rows]
                trends[field] = _trend_stats(values, years)

        return json.dumps({"raw": data, "trends": trends}, ensure_ascii=False, indent=2)


# ===== SegmentTrendBatchTool =====

class SegmentTrendBatchInput(BaseModel):
    segment_names: list[str]    # セグメント名リスト（例: ["日本", "EMEA", "Americas", "APAC"]）
    segment_values: list[list]  # 各セグメントの数値リスト（古い順・Noneを含んでよい）
    years: list[int]            # 共通年度リスト（segment_valuesの各リストと対応）


class SegmentTrendBatchTool(BaseTool):
    """
    複数セグメントのCAGR・トレンド方向・直近変化率・最新年度構成比を一括計算する。

    TrendAnalysisTool をセグメント数だけ個別に呼び出す代わりに、
    このツールを1回呼ぶだけで全セグメントのトレンドと構成比を取得できる。

    返却値（JSON）:
      {
        "日本": { "cagr": 0.045, "trend": "改善", "recent_3yr_change_rate": 0.14,
                  "latest": 6083.0, "oldest": 5327.0, "years": [...],
                  "latest_weight": 0.41 },   ← 最新年度の売上構成比（全セグメント合計=1）
        "EMEA": { ... },
        ...
      }

    segment_names と segment_values は同じ順・同じ長さで渡すこと。
    years は全セグメント共通の年度リスト（古い順）。
    値が存在しない年は None を渡すと自動除去する。
    """
    name: str = "SegmentTrendBatchTool"
    description: str = (
        "複数セグメントのCAGR・トレンド方向・直近変化率・最新年度構成比を1回の呼び出しで一括計算する。"
        "segment_names: セグメント名リスト, "
        "segment_values: 各セグメントの数値リスト（古い順, Noneを含んでよい）, "
        "years: 共通年度リスト（int）。"
        "TrendAnalysisTool をセグメント数だけ個別に呼ぶ代わりにこのToolを使うこと。"
        "返却値に latest_weight（最新年度の売上構成比）が含まれるため、"
        "後続エージェントがセグメント別加重平均CAGRを直接計算できる。"
    )
    args_schema: type[BaseModel] = SegmentTrendBatchInput

    def _run(self, segment_names: list, segment_values: list, years: list) -> str:
        if len(segment_names) != len(segment_values):
            return json.dumps(
                {"error": "segment_names と segment_values の長さが一致しません"},
                ensure_ascii=False,
            )

        results: dict = {}
        latest_vals: dict = {}

        for name, vals in zip(segment_names, segment_values):
            stats = _trend_stats(vals, years)
            results[name] = stats
            if "latest" in stats and stats["latest"] is not None:
                latest_vals[name] = stats["latest"]

        # 最新年度の構成比を計算（全セグメントの latest 合計を 1 とする）
        total = sum(v for v in latest_vals.values() if v and v > 0)
        if total > 0:
            for name in results:
                if name in latest_vals and latest_vals[name] and latest_vals[name] > 0:
                    results[name]["latest_weight"] = round(latest_vals[name] / total, 4)

        # 加重平均CAGR（各セグメントの latest_weight × cagr の合計）
        weighted_cagr = None
        cagr_parts = [
            results[name]["latest_weight"] * results[name]["cagr"]
            for name in results
            if results[name].get("latest_weight") is not None
            and results[name].get("cagr") is not None
        ]
        if cagr_parts:
            weighted_cagr = round(sum(cagr_parts), 4)

        return json.dumps(
            {"segments": results, "weighted_avg_cagr": weighted_cagr},
            ensure_ascii=False,
            indent=2,
        )
