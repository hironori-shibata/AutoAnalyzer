# 技術スタック設計書

## 実行環境

| 項目 | 内容 |
|---|---|
| パッケージ管理 | Anaconda (conda + pip) |
| Python バージョン | 3.11以上推奨 |
| 仮想環境名 | `autoanalyzer` |

```bash
conda create -n autoanalyzer python=3.11
conda activate autoanalyzer
pip install -r requirements.txt
```

---

## 依存ライブラリ一覧

### コアフレームワーク

| ライブラリ | 用途 |
|---|---|
| `crewai` | Multi-Agent オーケストレーション |
| `crewai-tools` | CrewAI標準ツール群 |

> **廃止:** LlamaIndex (llama-index 系) は廃止。RAGを廃止し生データ直読み方式に移行済み。
> `langchain` / `langchain-community` も不使用。

### LLM

| ライブラリ | 用途 |
|---|---|
| `litellm`（crewai内部） | DeepSeek API呼び出し（OpenAI互換エンドポイント使用） |

```python
# DeepSeek API設定（実装済み: src/config.py）
from crewai import LLM

def get_llm() -> LLM:
    return LLM(
        model="openai/deepseek-chat",   # DeepSeek v3
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
        temperature=0.2,
        timeout=400,    # PDF変換等の長時間処理を考慮し400秒
    )

def get_reasoner_llm() -> LLM:
    """DeepSeek R1 (Reasoner) ※ツール呼び出しが不安定なため基本は使用しない"""
    return LLM(
        model="openai/deepseek-reasoner",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
        timeout=400,
    )
```

> **注意:** `deepseek-reasoner` はFunction Calling(ツール呼び出し)との互換性が低い。
> 現状はすべてのAgentで `deepseek-chat` (V3) を使用する。

### データ取得・スクレイピング

| ライブラリ | 用途 |
|---|---|
| `requests` | HTTP取得 |
| `beautifulsoup4` | HTMLパース |
| `ddgs` (`duckduckgo-search`) | DuckDuckGO検索 ※パッケージ名が `ddgs` に改名 |
| `docling` | PDF → Markdown変換 |
| `pandas` | テーブルパース・CSV操作 |

> **Jina Reader** はAPIキー不要の `https://r.jina.ai/{url}` エンドポイントを利用する。
> スクレイピング困難なページのフォールバックとして使用。

### Slack連携

| ライブラリ | 用途 |
|---|---|
| `slack-bolt` | Slack Botフレームワーク |
| `slack-sdk` | Slack API クライアント |

### ユーティリティ

| ライブラリ | 用途 |
|---|---|
| `numpy` | 数値計算（TrendAnalysisTool） |
| `python-dotenv` | 環境変数管理 |
| `pydantic` | データバリデーション |
| `loguru` | ロギング |

---

## requirements.txt（現行）

```
crewai
crewai-tools
ddgs
requests
beautifulsoup4
docling
slack-bolt
slack-sdk
pandas
numpy
python-dotenv
pydantic
loguru
```

---

## 環境変数 (.env)

```
# LLM
DEEPSEEK_API_KEY=your_deepseek_api_key

# Slack
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...   # Socket Modeを使う場合
SLACK_SIGNING_SECRET=...

# Edinet
EDINET_API_KEY=your_edinet_api_key
```

> **廃止:** `OPENAI_API_KEY` はLlamaIndexのEmbedding用として記載されていたが不要。
> LlamaIndexそのものを廃止したため削除。

---

## 外部API

| API | 認証方式 | 用途 |
|---|---|---|
| Edinet API | APIキー（無料取得） | 有価証券報告書のdocumentcode取得 |
| DeepSeek API | APIキー | LLM推論（deepseek-chat V3） |
| Slack API | Bot Token / App Token | Slack連携 |
| DuckDuckGO | 不要 | Web検索（中国語サイト除外フィルタあり） |
| Jina Reader | 不要（制限あり） | Webページ取得 |
