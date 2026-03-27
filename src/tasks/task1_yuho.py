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
            "有価証券報告書から以下の情報をすべて収集してください:\n"
            "1. 事業内容とセグメント構成\n"
            "   URL: https://irbank.net/{edinet_code}/business?f={document_code}\n"
            "2. リスク情報（上位5件）: 各リスクについて、事業への影響度（大・中・小）を判定し、その根拠を簡潔に記述すること。判断にあたっては、利益率の高さやコスト構造（設備投資の重さ等）を考慮すること。\n"
            "   URL: https://irbank.net/{edinet_code}/risk?f={document_code}\n"
            "3. 経営課題\n"
            "   URL: https://irbank.net/{edinet_code}/task?f={document_code}\n"
            "4. 研究開発の状況\n"
            "   URL: https://irbank.net/{edinet_code}/rd?f={document_code}\n"
            "5. 大株主構成（上位10位）\n"
            "   URL: https://irbank.net/{edinet_code}/notes/MajorShareholdersTextBlock?f={document_code}\n"
            "6. 親会社・連結会社の関係\n"
            "   URL: https://irbank.net/{edinet_code}/af?f={document_code}\n"
            "7. 従業員状況（人数・平均年齢・平均年収）\n"
            "   URL: https://irbank.net/{edinet_code}/notes/InformationAboutEmployeesTextBlock?f={document_code}\n"
            "8. 会社沿革のハイライト\n"
            "   URL: https://irbank.net/{edinet_code}/history?f={document_code}\n"
            "9. 設備状況の概要\n"
            "   URL: https://irbank.net/{edinet_code}/facilities?f={document_code}\n\n"
            "各URLにアクセスする際は必ず1秒以上の間隔を空けること。"
        ).format(edinet_code=edinet_code, document_code=document_code),
        expected_output=(
            "【緩和条件】情報が完全に揃わなくても構いません。取得できない場合は「該当データなし」と記載して次に進み、情報の深追いや無限ループを避けてください。\n"
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
