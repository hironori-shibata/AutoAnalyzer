"""
Agent2: ライバルリサーチャー
対象企業の競合他社・業界構造を調査する。
DuckDuckGO検索ツールを活用して最新の業界動向・競合比較情報を収集する。
"""
from crewai import Agent
from src.config import get_llm
from src.tools.web_search import WebSearchTool
from src.tools.stock_scraper import StockScraperTool


def create_agent2() -> Agent:
    llm = get_llm()
    return Agent(
        role="ライバルリサーチャー",
        goal=(
            "対象企業の競合環境・業界構造を深く調査し、"
            "当該企業の競争優位性と脅威を明確にすること。"
        ),
        backstory=(
            "あなたは業界アナリストとして、競合比較と業界構造分析を専門としています。"
            "ウェブ検索や関連サイトの最新情報を最大限活用して、投資判断に必要な競争環境の全体像を描きます。"
        ),
        tools=[WebSearchTool(), StockScraperTool()],
        llm=llm,
        verbose=True,
        max_iter=15,  # 長時間調査するため緩和
    )
