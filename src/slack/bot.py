"""
Slack Bot イベントハンドラ
Socket Mode で起動し、4桁の証券番号メッセージを検知して分析を起動する。
"""
import os
import re
from loguru import logger
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import concurrent.futures

from src.crew import run_analysis
from src.slack.sender import send_report

app = App(token=os.environ["SLACK_BOT_TOKEN"])

TICKER_PATTERN = re.compile(r"^\s*(\d{4})\s*$")

# グローバルなスレッドプールエグゼキュータ（CrewAIのテレメトリ通信用にContextを保持させる）
executor = concurrent.futures.ThreadPoolExecutor(max_workers=5)


@app.message(re.compile(r"^(?!\s*\d{4}\s*$)"))
def handle_invalid(message, say):
    """4桁の証券番号以外のメッセージを受信したときの処理"""
    thread_ts = message.get("thread_ts") or message["ts"]
    say(
        text="4桁の銘柄コードを送信してください（例: `7203`）。",
        thread_ts=thread_ts,
    )


@app.message(TICKER_PATTERN)
def handle_ticker(message, say, client):
    """4桁の証券番号を受信したときの処理"""
    match = TICKER_PATTERN.search(message["text"])
    if not match:
        return

    ticker = match.group(1)
    channel = message["channel"]
    thread_ts = message.get("thread_ts") or message["ts"]

    logger.info(f"証券番号受信: {ticker} (channel: {channel})")

    # 即時返信
    say(
        text=f"証券番号 *{ticker}* の企業価値分析を開始します。しばらくお待ちください 🔍",
        thread_ts=thread_ts,
    )

    def run():
        """バックグラウンドスレッドで分析を実行"""
        try:
            # スレッド内での環境変数の確認用ログ
            tracing_status = os.environ.get("CREWAI_TRACING_ENABLED", "false")
            logger.info(f"子スレッド分析開始: CREWAI_TRACING_ENABLED={tracing_status}")

            report = run_analysis(ticker)
            send_report(client, channel, thread_ts, ticker, report)
        except Exception as e:
            logger.exception(f"分析エラー ({ticker}): {e}")
            client.chat_postMessage(
                channel=channel,
                thread_ts=thread_ts,
                text=f"❌ 分析に失敗しました: {str(e)}",
            )

    # ThreadPoolExecutor を使用してスレッドをキックする
    # threading.Thread と異なり、Python3.9以降では ContextVar (OpenTelemetry用) が伝播しやすくなる
    executor.submit(run)


def start_bot():
    """Slack Socket Mode でBotを起動する"""
    handler = SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"])
    logger.info("Slack Bot 起動済み。メッセージ待受中...")
    handler.start()
