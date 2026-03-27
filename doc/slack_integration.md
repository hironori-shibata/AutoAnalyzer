# Slack連携設計書

## 概要

Slack Bolt (Socket Mode) を使用し、特定チャンネルへの4桁証券番号メッセージを検知して分析を起動する。  
レポートは長文になるため、Slackのファイルアップロード機能を使ってMarkdownファイルとして送信する。

---

## フロー

```
1. ユーザーがSlackチャンネルに「7203」と送信
2. Slack Botが証券番号(4桁数字)を正規表現で検知
3. 「分析を開始します。しばらくお待ちください 🔍」と即時返信
4. バックグラウンドスレッドで crew.run_analysis(ticker) を起動
5. 完了後、レポートをSlackのスニペット/ファイルとして同チャンネルに送信
6. エラー時は「分析に失敗しました: {エラー内容}」をチャンネルに返信
```

---

## 実装仕様

### `src/slack/bot.py`

```python
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import threading
import re
from src.crew import run_analysis
from src.slack.sender import send_report
from loguru import logger
import os

app = App(token=os.environ["SLACK_BOT_TOKEN"])

TICKER_PATTERN = re.compile(r"^\s*(\d{4})\s*$")

@app.message(TICKER_PATTERN)
def handle_ticker(message, say, client):
    ticker = TICKER_PATTERN.search(message["text"]).group(1)
    channel = message["channel"]
    thread_ts = message.get("thread_ts") or message["ts"]

    say(
        text=f"証券番号 *{ticker}* の企業価値分析を開始します。しばらくお待ちください 🔍",
        thread_ts=thread_ts,
    )

    def run():
        try:
            report = run_analysis(ticker)
            send_report(client, channel, thread_ts, ticker, report)
        except Exception as e:
            logger.exception(e)
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"❌ 分析に失敗しました: {str(e)}",
            )

    threading.Thread(target=run, daemon=True).start()


def start_bot():
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    handler.start()
```

---

### `src/slack/sender.py`

```python
from slack_sdk import WebClient
from loguru import logger

def send_report(client: WebClient, channel: str, thread_ts: str, ticker: str, report: str):
    """
    レポートをSlackに送信する。
    長文のためファイルアップロードを使用。
    """
    filename = f"analysis_{ticker}.md"

    try:
        # files_upload_v2 (新API)
        client.files_upload_v2(
            channel=channel,
            thread_ts=thread_ts,
            content=report,
            filename=filename,
            title=f"企業価値分析レポート: {ticker}",
            initial_comment=f"✅ *{ticker}* の分析が完了しました。",
        )
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        # フォールバック: 分割テキスト送信
        _send_long_text(client, channel, thread_ts, report)


def _send_long_text(client: WebClient, channel: str, thread_ts: str, text: str):
    """3000文字ごとに分割して送信するフォールバック"""
    CHUNK_SIZE = 3000
    chunks = [text[i:i+CHUNK_SIZE] for i in range(0, len(text), CHUNK_SIZE)]
    for i, chunk in enumerate(chunks):
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"```{chunk}```" if i > 0 else chunk,
        )
```

---

## `src/main.py`

```python
from dotenv import load_dotenv
load_dotenv()

from src.slack.bot import start_bot
from loguru import logger

if __name__ == "__main__":
    logger.info("AutoAnalyzer Bot 起動中...")
    start_bot()
```

---

## Slack App設定（管理コンソール）

| 設定項目 | 値 |
|---|---|
| Socket Mode | 有効化 |
| Event Subscriptions | `message.channels`, `message.groups`, `message.im` |
| Bot Token Scopes | `chat:write`, `files:write`, `channels:history`, `groups:history`, `im:history` |
| App Token Scopes | `connections:write` |

---

## 動作確認手順

```bash
conda activate autoanalyzer
cp .env.example .env
# .env に各APIキーを記入

python src/main.py
# Slackチャンネルに「7203」と送信して動作確認
```
