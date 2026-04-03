"""
Agent1: 有報リサーチャー
有価証券報告書から企業の定性情報・事業内容・リスク・大株主構造などを収集する。
"""
from crewai import Agent
from src.config import get_llm
from src.tools.irbank_yuho_tool import IRBankYuhoTool


def create_agent1() -> Agent:
    return Agent(
        role="有報リサーチャー",
        goal=(
            "有価証券報告書から企業の事業内容・リスク・大株主構造・従業員状況などの"
            "定性情報を網羅的に収集し、企業の本質的な姿を明らかにすること。"
        ),
        backstory=(
            "あなたは企業のIR資料を深く読み込む専門家です。"
            "有価証券報告書の各セクションから重要な情報を抽出し、"
            "投資判断に役立つ定性分析を提供することを得意としています。"
        ),
        tools=[IRBankYuhoTool()],
        llm=get_llm(),
        verbose=True,
        max_iter=5,
    )
