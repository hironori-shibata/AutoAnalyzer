"""
Task1: 有報リサーチタスク
Agent1 (有報リサーチャー) が担当する。
"""
from crewai import Task
from src.agents.agent1_yuho import create_agent1


def create_task1(ticker: str, edinet_code: str, document_code: str) -> Task:
    agent = create_agent1()
    return Task(
        description=(
            f"証券番号 {ticker}（EdinetCode: {edinet_code}, documentcode: {document_code}）の"
            "有価証券報告書から定性情報を収集してください。\n\n"
            f"IRBankYuhoTool を edinet_code='{edinet_code}', document_code='{document_code}' で"
            "1回呼び出すと、以下9項目のテキストがまとめて返されます:\n"
            "1. 事業内容とセグメント構成\n"
            "2. リスク情報（上位5件）\n"
            "3. 経営課題\n"
            "4. 研究開発の状況\n"
            "5. 大株主構成（上位10位）\n"
            "6. 親会社・連結会社の関係\n"
            "7. 従業員状況（人数・平均年齢・平均年収）\n"
            "8. 会社沿革のハイライト\n"
            "9. 設備状況の概要\n\n"
            "取得したテキストを整理し、各項目をMarkdownレポートにまとめてください。\n"
            "「2. リスク情報」は各リスクについて事業への影響度（大・中・小）を判定し、"
            "利益率やコスト構造を考慮した根拠を記述すること。"
        ),
        expected_output=(
            "【緩和条件】情報が完全に揃わなくても構いません。取得できない場合は「該当データなし」と記載して次に進んでください。\n"
            "上記9項目を網羅したMarkdown形式のレポート。\n"
            "各項目に見出しを付け、箇条書きや表を適宜使用すること。\n"
            "特に「2. リスク情報」については、必ず以下のJSON形式を含めること:\n"
            "```json\n"
            "[\n"
            "  {\n"
            "    \"risk\": \"リスク項目名\",\n"
            "    \"impact\": \"大 or 中 or 小\",\n"
            "    \"reasoning\": \"影響度判定の具体的な根拠（例: 原価率が低いため赤字転落リスクは低い、設備コストが重いため台数減の打撃が大きい等）\"\n"
            "  }\n"
            "]\n"
            "```"
        ),
        agent=agent,
    )
