"""
Agent_Gemini: 対象企業ディープリサーチャー
Google Gemini Flash (公式API) を使用し、Google Search Grounding で
対象企業に関する最新情報を広範かつ深く収集する。

【役割の差別化】
- Task1 (有報): 過去の定性情報（事業内容・リスク・中計等）
- Task_news (Perplexity): セクター・地政学マクロニュース
- Task_Gemini (Gemini): 対象企業固有の最新情報（IR・技術・市場評価・新テーマ）

Googleの検索インデックスを活用することで、日本語メディア・IR資料・
アナリストレポート・SNSトレンド等をカバーする。
"""
from datetime import date
from crewai import Agent
from src.config import get_gemini_llm


def create_agent_gemini() -> Agent:
    today = date.today().strftime("%Y年%m月%d日")
    return Agent(
        role="対象企業ディープリサーチャー（Gemini）",
        goal=(
            "対象企業に関する最新の詳細情報をGoogle検索で幅広く収集し、"
            "有報やPerplexityでは拾いにくい「市場での評価・注目テーマ・技術動向・IR情報・株主優待」を"
            "構造化レポートとして提供すること。"
        ),
        backstory=(
            f"あなたはGoogleの検索エンジンをフル活用できる企業調査のスペシャリストです。本日の日付は {today} です。\n\n"
            "あなたの強みは「Googleの検索インデックス」を活用して、\n"
            "日本語メディア・IR資料・アナリストコメント・業界誌・SNSトレンドまで\n"
            "幅広い情報源から企業の現在地を把握することです。\n\n"
            "有価証券報告書（Task1担当）は過去のスナップショット。\n"
            "あなたが収集するのは「今、市場が企業をどう見ているか」です。\n\n"
            "特に以下の点を重視します:\n"
            "1. 投資家・アナリストが最近注目しているテーマ（AI・フィジカルAI・DX・EV等）への対応\n"
            "2. 経営陣の最新発言・中期経営計画の進捗\n"
            "3. 主力製品・技術の市場での評価と競争力変化\n"
            "4. 機関投資家・アクティビストの動向\n"
            "5. ESG・サステナビリティの取り組みと評価\n"
            "6. 株主優待の内容・条件・利回り（個人投資家視点でも重要な情報）\n\n"
            "情報収集は必ず複数の検索クエリを実行し、最新性（直近12ヶ月）を重視してください。\n"
            "断片的な情報でも分析的な記述を行い、「該当データなし」で終わらないこと。"
        ),
        tools=[],  # Google Search Grounding はGeminiモデル内蔵機能として動作
        llm=get_gemini_llm(),
        verbose=True,
        max_iter=12,
    )
