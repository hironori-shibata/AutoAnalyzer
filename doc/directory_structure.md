# ディレクトリ・ファイル構成設計書

## 全体構成

```
AutoAnalyzer/                         # rootディレクトリ
├── .env                              # 環境変数（gitignore対象）
├── .env.example                      # 環境変数テンプレート
├── .gitignore
├── requirements.txt
├── README.md
│
├── data/                             # 銘柄ごとの取得データ（LlamaIndex用）
│   ├── 7203/                         # 証券番号ごとのディレクトリ
│   │   ├── kessan_tansin.md          # 決算短信(Markdown変換済み)
│   │   ├── yuho_business.md          # 有報: 事業内容
│   │   ├── yuho_risk.md              # 有報: リスク情報
│   │   ├── yuho_rd.md                # 有報: 研究開発
│   │   └── ...                       # その他有報セクション
│   └── 9432/
│       └── ...
│
├── doc/                              # 設計書（本ディレクトリ）
│   ├── README.md
│   ├── architecture.md
│   ├── tech_stack.md
│   ├── directory_structure.md        # 本ファイル
│   ├── data_sources.md
│   ├── slack_integration.md
│   ├── agents/
│   │   ├── agent1_yuho_researcher.md
│   │   ├── agent2_rival_researcher.md
│   │   ├── agent3_kessan_researcher.md
│   │   ├── agent4_performance_researcher.md
│   │   ├── agent5_stock_researcher.md
│   │   └── agent6_manager.md
│   └── tools/
│       ├── calculation_tools.md
│       └── scraping_tools.md
│
└── src/                              # 実装コード
    ├── main.py                       # エントリーポイント（Slack Bot起動）
    ├── crew.py                       # CrewAI Crew/Flow定義
    ├── config.py                     # 設定・定数管理
    │
    ├── agents/                       # Agent定義
    │   ├── __init__.py
    │   ├── agent1_yuho.py
    │   ├── agent2_rival.py
    │   ├── agent3_kessan.py
    │   ├── agent4_performance.py
    │   ├── agent5_stock.py
    │   └── agent6_manager.py
    │
    ├── tasks/                        # CrewAI Task定義
    │   ├── __init__.py
    │   ├── task1_yuho.py
    │   ├── task2_rival.py
    │   ├── task3_kessan.py
    │   ├── task4_performance.py
    │   ├── task5_stock.py
    │   └── task6_report.py
    │
    ├── tools/                        # Python Toolクラス
    │   ├── __init__.py
    │   ├── financial_calc.py         # 財務指標計算Tool
    │   ├── valuation_calc.py         # DCF・マルチプル計算Tool
    │   ├── irbank_scraper.py         # IR Bankスクレイパー
    │   ├── kessan_fetcher.py         # 決算短信取得・PDF変換
    │   ├── shikiho_scraper.py        # 四季報スクレイパー
    │   ├── stock_scraper.py          # 株価・需給スクレイパー
    │   ├── edinet_client.py          # Edinet APIクライアント
    │   └── web_search.py             # DuckDuckGO検索ラッパー
    │
    ├── utils/                        # ユーティリティ
    │   ├── __init__.py
    │   ├── code_converter.py         # 証券番号→EdinetCode変換
    │   ├── llama_index_manager.py    # LlamaIndexインデックス管理
    │   └── report_formatter.py       # レポートフォーマット整形
    │
    └── slack/                        # Slack連携
        ├── __init__.py
        ├── bot.py                    # Slackイベントハンドラ
        └── sender.py                 # Slackメッセージ送信
```

---

## 重要ファイルの責務

### `src/main.py`
- Slack Botを起動し、証券番号の受信を待機する
- 受信後、`crew.py` の `run_analysis(ticker)` を呼び出す
- 非同期処理でSlackがタイムアウトしないよう注意

### `src/crew.py`
- CrewAI の `Crew` インスタンスを生成・管理
- Agent1〜5を並列(Phase1)、Agent6を逐次(Phase2)で実行
- 最終レポート文字列を返す

### `src/utils/code_converter.py`
- `data/edinet_code_list.csv` を読み込み、4桁の証券番号からEdinetCodeへ変換
- EdinetCodeからEdinet APIのdocumentcodeを取得するロジックも含む

### `src/utils/llama_index_manager.py`
- `data/{ticker}/` 以下のMarkdownファイルをインデックス化
- Agent6のRAGクエリに対してコンテキストを返す

---

## データディレクトリ管理ルール

- `data/{ticker}/` は実行時に自動生成される
- 同じ銘柄を再分析する場合、既存ファイルを上書きして再インデックスを行う
- `.gitignore` に `data/` を追加し、取得データをコミットしない

```gitignore
# .gitignore
.env
data/
__pycache__/
*.pyc
.DS_Store
```
