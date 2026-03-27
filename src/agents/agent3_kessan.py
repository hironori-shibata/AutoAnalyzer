"""
Agent3: 最新決算短信リサーチャー
IR Bankから最新の決算短信PDFを取得・Markdown変換し、
Python Toolを使って各種財務指標を計算する。
LLMには計算をさせない。
"""
from crewai import Agent
from src.config import get_llm
from src.tools.kessan_fetcher import KessanFetcherTool
from src.tools.financial_calc import FinancialCalcTool
from src.tools.file_reader import MarkdownReadTool


def create_agent3() -> Agent:
    return Agent(
        role="最新決算短信リサーチャー",
        goal=(
            "最新の決算短信PDFを取得・解析し、"
            "財務指標をPython Toolで正確に計算すること。"
            "絶対にLLM自身で数値計算を行わないこと。"
        ),
        backstory=(
            "あなたは財務データの抽出と分析の専門家です。"
            "決算短信から正確な数値を抽出し、Python Toolに計算を委ねることで"
            "信頼性の高い財務指標を提供します。"
        ),
        tools=[KessanFetcherTool(), FinancialCalcTool(), MarkdownReadTool()],
        llm=get_llm(),
        verbose=True,
        max_iter=25,
    )
