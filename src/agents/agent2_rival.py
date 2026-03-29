"""
Agent2: ライバルリサーチャー
対象企業の競合他社・業界構造を調査する。
Perplexity Sonar (OpenRouter経由) を使用。ウェブ検索はモデル内蔵機能で実行する。
定量データ（PER/PBR等）は Agent2a が収集済みのため、本エージェントは定性分析に集中する。
"""
from crewai import Agent
from src.config import get_perplexity_llm


def create_agent2() -> Agent:
    llm = get_perplexity_llm()
    return Agent(
        role="ライバルリサーチャー",
        goal=(
            "対象企業の競合環境・業界構造を深く調査し、"
            "当該企業の競争優位性と脅威を明確にすること。"
        ),
        backstory=(
            "あなたは業界アナリストとして、競合比較と業界構造分析を専門としています。"
            "ウェブ検索の最新情報を最大限活用して、投資判断に必要な競争環境の全体像を描きます。"
        ),
        tools=[],
        llm=llm,
        verbose=True,
        max_iter=15,
    )
