# AutoAnalyzer

Slackに4桁の証券番号を入力するだけで、複数のAI Agentが協調して企業価値分析レポートを生成・送信するシステム。

## システム概要

- **Agent1**: 有報リサーチャー（有価証券報告書から定性情報収集）
- **Agent2**: ライバルリサーチャー（競合・業界構造調査）
- **Agent3**: 決算短信リサーチャー（最新決算PBF取得・財務指標計算）
- **Agent4**: 業績リサーチャー（複数年業績トレンド分析）
- **Agent5**: 株価・需給リサーチャー（需給データ分析）
- **Agent6**: 統括マネージャー（DCF・マルチプル法で企業価値算定・レポート生成）

## 前提条件

- Anaconda (conda) がインストール済みであること
- Python 3.11以上

## セットアップ

### 1. conda環境の作成

```bash
conda create -n autoanalyzer python=3.11
conda activate autoanalyzer
pip install -r requirements.txt
```

### 2. Edinet コードリストの取得

[Edinet公式サイト](https://disclosure2.edinet-fsa.go.jp/weee0010.aspx) から `EdinetcodeDlInfo.zip` をダウンロードし、解凍した CSV ファイルを `data/edinet_code_list.csv` として配置してください。

### 3. 環境変数の設定

```bash
cp .env.example .env
# .env を編集して各APIキーを設定
```

必要なAPIキー:
- `DEEPSEEK_API_KEY`: [DeepSeek](https://platform.deepseek.com/) から取得
- `SLACK_BOT_TOKEN` / `SLACK_APP_TOKEN` / `SLACK_SIGNING_SECRET`: Slack App管理コンソールから取得
- `EDINET_API_KEY`: [Edinet API](https://disclosure2.edinet-fsa.go.jp/weee0020.aspx) から取得（無料）
- `OPENAI_API_KEY`: (オプション) LlamaIndex Embedding用

### 4. Slack App設定

| 設定項目 | 値 |
|---|---|
| Socket Mode | 有効化 |
| Event Subscriptions | `message.channels`, `message.groups`, `message.im` |
| Bot Token Scopes | `chat:write`, `files:write`, `channels:history`, `groups:history`, `im:history` |
| App Token Scopes | `connections:write` |

## 起動

```bash
conda activate autoanalyzer
python src/main.py
```

Slackチャンネルに「7203」（4桁証券番号）を送信すると分析が開始されます。

## ディレクトリ構成

```
AutoAnalyzer/
├── .env                  # 環境変数（gitignore対象）
├── .env.example          # 環境変数テンプレート
├── requirements.txt
├── README.md
├── data/                 # 取得データ（gitignore対象）
│   └── edinet_code_list.csv  # Edinet公式CSVを配置
├── doc/                  # 設計書
└── src/                  # 実装コード
    ├── main.py
    ├── crew.py
    ├── config.py
    ├── agents/
    ├── tasks/
    ├── tools/
    ├── utils/
    └── slack/
```

## 重要な制約事項

- **LLMに計算をさせない**: 数値計算は必ずPython Toolに委譲
- **スクレイピング時は1秒以上のウェイトを挿入**
- 信用倍率は「高い＝良い」ではない（Agent5参照）
- 単一時点の数値ではなく**時系列変化**を分析の軸とする
