# AutoAnalyzer

Slackに4桁の証券コードを送るだけで、**複数の専門AIエージェントが自動協調**し、プロレベルの企業価値分析レポートをSlackに返送するシステムです。

---

## デモ

```
[あなた → Slack] 7203
[Bot → Slack]    ✅ トヨタ自動車(7203)の分析を開始します...
（数分後）
[Bot → Slack]    📊 企業価値分析レポート（Markdown・PDFファイル添付）
```

---

## 特徴

- **完全自動化**: 証券コードを投げるだけ。データ収集〜レポート生成まで全自動
- **12段階のAIパイプライン**: 有報・決算短信・競合・需給・ニュース・DCF・ショートレポート・最終投資判断まで網羅
- **複数LLM活用**: DeepSeek v3 / Gemini Flash / Perplexity Sonar / ChatGPT / DeepSeek R1 をタスクに応じて使い分け
- **LLMに計算させない**: DCF・マルチプル等の数値計算は全てPythonツールが担当し、LLMの幻覚リスクを排除
- **ブル・ベア対立構造**: Agent6（買いレポート）→ Agent7（ショートレポート）→ Agent8（最終判断）で恣意的な楽観論を排除

---

## アーキテクチャ

### パイプライン全体図

```
Slack受信 → [12タスク 逐次実行] → Slackレポート送信
               │
               ├─ Task1:  有報リサーチャー         (DeepSeek v3)
               ├─ TaskG:  企業ディープリサーチ     (Gemini Flash + Google検索)
               ├─ Task2:  競合・業界調査           (DeepSeek v3)
               ├─ Task2a: 競合財務データ収集       (DeepSeek v3)
               ├─ Task2b: 競合比較レポート生成     (DeepSeek v3)
               ├─ Task3:  決算短信解析             (DeepSeek v3)
               ├─ Task4:  業績トレンド分析         (DeepSeek v3)
               ├─ Task5:  株価・需給分析           (DeepSeek v3)
               ├─ TaskN:  業界ニュース・地政学     (Perplexity Sonar)
               ├─ Task6:  統括レポート生成 (DCF)   (DeepSeek v3)  ← Task1〜TaskN全参照
               ├─ Task7:  ショートレポート         (ChatGPT via OpenRouter)
               └─ Task8:  最終投資判断             (DeepSeek R1)
```

### エージェント詳細

| エージェント | 役割 | 使用LLM | 主なデータソース |
|---|---|---|---|
| Agent1 有報リサーチャー | 有価証券報告書から事業内容・リスク・中計等の定性情報収集 | DeepSeek v3 | IR Bank, Jina Reader |
| Agent_Gemini ディープリサーチャー | Google検索でIR情報・技術動向・市場評価・注目テーマを収集 | Gemini Flash | Google Search Grounding |
| Agent2 競合リサーチャー | 競合企業・業界構造の調査 | DeepSeek v3 | DuckDuckGo, Web scraping |
| Agent2a 競合データ収集 | 競合企業の財務データを数値で収集 | DeepSeek v3 | IR Bank, kabutan |
| Agent2b 競合レポート生成 | 収集データから競合比較レポートを生成 | DeepSeek v3 | Task2/2a出力 |
| Agent3 決算短信リサーチャー | 最新決算短信PDF取得・財務指標計算 | DeepSeek v3 | IR Bank PDF, docling |
| Agent4 業績リサーチャー | 複数年の業績トレンド・成長率分析 | DeepSeek v3 | IR Bank 時系列データ |
| Agent5 需給リサーチャー | 株価・信用倍率・大株主・需給データ分析 | DeepSeek v3 | kabutan, karauri.net |
| Agent_News ニュースリサーチャー | 企業固有ニュース・業界動向・地政学リスク収集 | Perplexity Sonar | Webリアルタイム検索 |
| Agent6 統括マネージャー | 全情報集約、DCF・マルチプル法で企業価値算定、買いレポート生成 | DeepSeek v3 | Task1〜TaskN全出力 |
| Agent7 ショートアナリスト | Agent6の前提を破壊し、崩壊ポイントを特定するベアケース分析 | ChatGPT (OpenRouter) | Task6出力 |
| Agent8 最終投資意思決定者 | ブル・ベア両レポートを第三者精査し、確率加重で最終判断を下す | DeepSeek R1 | Task6+Task7出力 |

---

## 前提条件

- **Anaconda (conda)** がインストール済み
- **Python 3.11**
- 各種APIキー（下記参照）

---

## セットアップ

### 1. conda環境の作成・依存関係インストール

```bash
conda create -n autoanalyzer python=3.11
conda activate autoanalyzer
pip install -r requirements.txt
```

### 2. Edinet コードリストの配置

[Edinet公式開示サイト](https://disclosure2.edinet-fsa.go.jp/weee0010.aspx) から `EdinetcodeDlInfo.zip` をダウンロードし、解凍したCSVを以下のパスに配置：

```
data/edinet_code_list.csv
```

### 3. 環境変数の設定

```bash
cp .env.example .env
# .env を編集して各APIキーを設定
```

| 環境変数 | 説明 | 取得先 |
|---|---|---|
| `DEEPSEEK_API_KEY` | DeepSeek v3 / R1 用 | [DeepSeek Platform](https://platform.deepseek.com/) |
| `SLACK_BOT_TOKEN` | Slack Bot トークン (`xoxb-...`) | Slack App管理コンソール |
| `SLACK_APP_TOKEN` | Slack App トークン (`xapp-...`) | Slack App管理コンソール |
| `SLACK_SIGNING_SECRET` | Slack署名シークレット | Slack App管理コンソール |
| `EDINET_API_KEY` | Edinet API キー（無料） | [Edinet API](https://disclosure2.edinet-fsa.go.jp/weee0020.aspx) |
| `GEMINI_API_KEY` | Google Gemini Flash 用 | [Google AI Studio](https://aistudio.google.com/) |
| `OPENROUTER_API_KEY` | Perplexity Sonar / ChatGPT 用 | [OpenRouter](https://openrouter.ai/) |

### 4. Slack App設定

Slack App管理コンソール（[api.slack.com/apps](https://api.slack.com/apps)）で以下を設定：

| 設定項目 | 値 |
|---|---|
| Socket Mode | 有効化 |
| Event Subscriptions | `message.channels`, `message.groups`, `message.im` |
| Bot Token Scopes | `chat:write`, `files:write`, `channels:history`, `groups:history`, `im:history` |
| App Token Scopes | `connections:write` |

---

## 起動

```bash
conda activate autoanalyzer
python src/main.py
```

起動後、SlackのチャンネルやDMに4桁の証券コードを送信すると分析が開始されます。

```
7203      # トヨタ自動車
6758      # ソニーグループ
9984      # ソフトバンクグループ
```

---

## 出力

- **Slackレポート**: 分析完了後、同スレッドにMarkdownレポートを送信
- **ローカル保存**: `data/{ticker}/` に全中間データ・レポートを保存

```
data/7203/
├── report.md               # 最終レポート
├── crew_execution.log      # 実行ログ
├── events.jsonl            # 全エージェントのステップ記録
└── ...                     # 各エージェントの中間出力
```

---

## ディレクトリ構成

```
AutoAnalyzer/
├── .env                    # 環境変数（gitignore対象）
├── .env.example            # 環境変数テンプレート
├── requirements.txt
├── README.md
├── data/                   # 取得データ・レポート（gitignore対象）
│   └── edinet_code_list.csv    # Edinet公式CSVを配置
├── doc/                    # 設計書・仕様書
│   ├── architecture.md
│   ├── tech_stack.md
│   ├── data_sources.md
│   ├── slack_integration.md
│   ├── agents/             # 各エージェント仕様
│   └── tools/              # 各ツール仕様
└── src/                    # 実装コード
    ├── main.py             # エントリーポイント（Slackボット起動）
    ├── crew.py             # パイプラインオーケストレーター
    ├── config.py           # LLM設定（DeepSeek/Gemini/OpenRouter等）
    ├── agents/             # 各エージェント定義
    ├── tasks/              # 各タスク定義
    ├── tools/              # データ収集・計算ツール群
    │   ├── financial_calc.py       # 財務指標計算（ROE, ROA, 利益率等）
    │   ├── valuation_calc.py       # DCF・マルチプル法バリュエーション
    │   ├── edinet_client.py        # Edinet API クライアント
    │   ├── kessan_fetcher.py       # 決算短信PDF取得
    │   ├── irbank_scraper.py       # IR Bank スクレイパー
    │   ├── stock_scraper.py        # 株価・需給データスクレイパー
    │   └── web_search.py           # DuckDuckGo 検索
    ├── utils/              # ユーティリティ
    └── slack/              # Slack送受信
        ├── bot.py          # メッセージ受信・分析トリガー
        └── sender.py       # レポート送信
```

---

## 設計上の重要ルール

- **LLMに計算させない**: DCF・PER・EV/EBITDAなどの数値計算は全てPythonツール関数が実行。LLMは解釈・文章生成のみ担当
- **スクレイピング遅延**: Webリクエスト間は必ず1秒以上の待機を挿入
- **単位自動検出**: DCF・マルチプルツールは「百万円 vs 円」の単位不整合を自動検出・補正
- **PDF処理**: doclingでPDF→Markdown変換後、エージェントが直接読取（RAG/埋め込み不使用）
- **エラー耐性**: データ取得失敗は graceful skip し、Agent6に欠損情報を通知してレポートを継続生成
- **需給シグナル解釈**: 信用倍率が高い＝買い圧過多（ネガティブ）、信用倍率低下＝需給改善（ポジティブ）

---

## ライセンス

MIT License
