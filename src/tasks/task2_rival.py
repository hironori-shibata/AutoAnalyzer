"""
Task2: ライバルリサーチタスク
Agent2 (ライバルリサーチャー) が担当する。
"""
from crewai import Task
from src.agents.agent2_rival import create_agent2


def create_task2(ticker: str, company_name: str = "") -> Task:
    agent = create_agent2()
    company_ref = company_name if company_name else f"証券番号{ticker}の企業"
    return Task(
        description=(
            f"証券番号 {ticker} の企業について、以下の競合調査を徹底的に実施してください:\n"
            "1. 対象企業の主要な競合他社（国内・海外問わず）を3〜5社程度特定\n"
            "2. 競合他社の証券番号（4桁）を特定し、StockScraperTool(source='kabutan_stock')で各社の詳細ページを取得し、PER、PBR、時価総額、利回り等の主要指標を抽出すること\n"
            "3. WebSearchToolを用いて、競合の最新動向や市場シェア、各社の強み・弱みを調べる\n"
            "4. {ticker}と競合他社の指標を比較し、相対的な投資魅力度を分析する\n"
            "⚠️ 情報が取得できない場合は「該当データなし」と記載してスキップして構いません。"
        ),
        expected_output=(
            "対象企業と競合他社を比較した詳細な競争環境レポート。\n"
            "各競合について、PER、PBR等の具体的数値を必ず記載すること。"
        ),
        agent=agent,
    )
