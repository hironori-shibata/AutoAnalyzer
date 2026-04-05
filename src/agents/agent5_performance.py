"""
Agent5: 業績トレンドリサーチャー
IR Bankから複数年（5〜10年分）の業績データを取得し、
時系列のトレンド変化を重視して分析する。
LLMには数値計算をさせない。
"""
from crewai import Agent
from src.config import get_llm
from src.tools.irbank_scraper import IRBankScraperTool
from src.tools.financial_calc import IRBankTrendBatchTool, SegmentTrendBatchTool


def create_agent5() -> Agent:
    return Agent(
        role="業績トレンドリサーチャー",
        goal=(
            "複数年にわたる業績データを収集し、時系列トレンドを分析すること。"
            "単一時点の数値ではなく、変化の方向性と持続性を重視すること。"
            "財務テーブル全指標のトレンド計算はIRBankTrendBatchTool(edinet_code)を1回呼ぶこと。"
            "IRBankFinancialTableToolを別途呼ぶ必要はない（バッチツールが内部で処理する）。"
            "セグメントデータは IRBankScraperTool で取得後、"
            "SegmentTrendBatchTool を1回呼ぶだけで全セグメントのCAGR・構成比を一括計算すること。"
            "TrendAnalysisTool をセグメントごとに個別に呼ぶことは禁止。"
        ),
        backstory=(
            "あなたは長期投資家の視点から企業の業績推移を分析する専門家です。"
            "5〜10年の時系列データから企業の実力と成長軌道を読み解きます。"
        ),
        tools=[IRBankTrendBatchTool(), IRBankScraperTool(), SegmentTrendBatchTool()],
        llm=get_llm(),
        verbose=True,
        max_iter=15,
    )
