"""
Task3a: 競合データ収集タスク
Agent3a (競合データ収集エージェント) が担当。
Task3 (Perplexity情報収集) が特定した競合他社リストをもとに、
StockScraperToolで各社の定量データを収集する。
"""
from crewai import Task
from src.agents.agent3a_rival_data import create_agent3a


def create_task3a(ticker: str, task3: Task) -> Task:
    agent = create_agent3a()
    return Task(
        description=(
            f"証券番号 {ticker} の企業の競合他社の財務指標を収集してください。\n\n"
            "【前提】Task3（Perplexity情報収集）がすでに主要競合他社を特定しています。\n"
            "Task3のSection 2に記載された競合他社リスト（社名・証券番号）を優先して使用してください。\n\n"
            "【手順】\n"
            f"1. Task3が特定した競合他社の証券番号を確認する（目標: 5〜7社）\n"
            "   ※ Task2で証券番号が記載されていない場合は自力で調べること\n\n"
            "2. 証券番号が5社に満たない場合は、以下の手順で株探テーマから補完すること:\n"
            f"   a) KabutanThemeListTool(ticker='{ticker}') を呼び出して対象企業のテーマ一覧を取得する\n"
            "   b) 取得したテーマ一覧を精査し、競合分析に有用なテーマ（業界・製品カテゴリ・技術等）を\n"
            "      1〜3件選ぶこと。以下は競合分析に不要なため除外すること:\n"
            "      ✗ 株価指数（TOPIX・JPX日経400・読売333 等）\n"
            "      ✗ マクロ・為替（円安メリット・ユーロ高 等）\n"
            "      ✗ 地域テーマ（中国関連・インド関連 等）\n"
            "      ✗ 投資スタイル（NISA関連・ESG投資・優待人気 等）\n"
            "      ✓ 選ぶべきテーマ例: 製品カテゴリ・業界名・技術領域（自動車・半導体・EV関連 等）\n"
            "   c) 選んだテーマURLそれぞれに対して KabutanThemeStocksTool(theme_url=...) を呼び出し、\n"
            "      銘柄コードと銘柄名の一覧を取得する\n"
            "      ※ URLは '/themes/?theme=...' の相対パスをそのまま渡してよい\n"
            "   d) 取得した銘柄リストから対象企業自身（証券番号 {ticker}）を除き、\n"
            "      競合候補を選定して証券番号リストに追加する\n\n"
            "3. 競合他社の証券番号リストが確定したら、以下のツールをそれぞれ1回ずつ呼び出すこと。\n"
            "   tickers に証券番号のリストをまとめて渡せば、全社分のデータが一括取得できる。\n"
            "   （例: tickers=[\"7267\", \"7269\", \"7270\", \"7201\", \"7205\"]）\n"
            "   ① KabutanBatchTool: PER・PBR・時価総額・配当利回りを一括取得\n"
            "   ② TradingViewEVEBITDATool: EV/EBITDA倍率を一括取得\n"
            "      ※ EV/EBITDAがマイナスの場合はTradingViewに表示されないことがある\n\n"
            "4. 対象企業が複数の異質セグメント（例: 自動車系と半導体系のように成長性が著しく異なるもの）を\n"
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
            "- 競合5〜7社のPER・PBR・時価総額・配当利回り・EV/EBITDAの具体的数値テーブル\n"
            "- （複数異質セグメントがある場合）セグメント別競合PERテーブル（セグメント名/競合社名/PER値/中央値）\n"
            "- データ取得できなかった企業・指標は「該当データなし」と明記"
        ),
        agent=agent,
        context=[task3],
    )
