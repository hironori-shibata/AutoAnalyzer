"""
Task2a: 競合データ収集タスク
Agent2a (競合データ収集エージェント) が担当。
Task2 (Perplexity情報収集) が特定した競合他社リストをもとに、
StockScraperToolで各社の定量データを収集する。
"""
from crewai import Task
from src.agents.agent2a_rival_data import create_agent2a


def create_task2a(ticker: str, task2: Task) -> Task:
    agent = create_agent2a()
    return Task(
        description=(
            f"証券番号 {ticker} の企業の競合他社の財務指標を収集してください。\n\n"
            "【前提】Task2（Perplexity情報収集）がすでに主要競合他社を特定しています。\n"
            "Task2のSection 2に記載された競合他社リスト（社名・証券番号）を優先して使用してください。\n"
            "Task2で証券番号が不明な企業は自分で調べること。\n\n"
            "【手順】\n"
            "1. Task2が特定した競合他社（5〜7社）の証券番号を確認する\n"
            "   ※ Task2で証券番号が記載されていない場合は自力で調べること\n"
            "   ※ 国内のみで5社に満たない場合は海外競合・グローバルプレイヤーも含めること\n"
            "2. 各競合他社の証券番号（4桁）を使い、StockScraperTool(source='kabutan_stock')で\n"
            "   各社の株探ページを取得し、以下の指標を抽出すること:\n"
            "   - PER、PBR、時価総額、配当利回り\n"
            "   ※ EV/EBITDAはデータ取得が不安定なため収集不要。PER・PBRのみで可。\n"
            "3. 対象企業が複数の異質セグメント（例: 自動車系と半導体系のように成長性が著しく異なるもの）を\n"
            "   持つ場合は、セグメントに対応する競合グループ別にPERを分けて収集すること:\n"
            "   - 各セグメントに対応する競合2〜3社のPERを収集\n"
            "   - セグメント名・競合社名・PER値・PER中央値をテーブルで示すこと\n"
            "     （例: 自動車セグメント=[日本特殊陶業13倍, NGK Spark Plug15倍] 中央値=14倍）\n"
            "   - これはAgent6のセグメント加重PER計算（MultiplesValuationToolの"
            "segment_median_persパラメータ）に使用される\n"
            "   ※ セグメントが1つ、または分類困難な場合は全体競合PERリストのみで可\n\n"
            "⚠️ データ取得に失敗した場合は「該当データなし」と記載してスキップして構いません。"
        ),
        expected_output=(
            "以下を含む競合他社データレポート:\n"
            "- 競合5〜7社のPER・PBR・時価総額・配当利回りの具体的数値テーブル\n"
            "- （複数異質セグメントがある場合）セグメント別競合PERテーブル（セグメント名/競合社名/PER値/中央値）\n"
            "- データ取得できなかった企業は「該当データなし」と明記"
        ),
        agent=agent,
        context=[task2],
    )
