"""
Slackメッセージ送信モジュール
レポートをファイルアップロード（files_upload_v2）で送信する。
送信失敗時は3000文字ごとに分割テキスト送信にフォールバック。
"""
from loguru import logger
from slack_sdk import WebClient


def send_report(
    client: WebClient,
    channel: str,
    thread_ts: str,
    ticker: str,
    report: str,
) -> None:
    """
    企業価値分析レポートをSlackに送信する。
    長文のため files_upload_v2 を使用してMarkdownファイルとしてアップロード。
    """
    filename = f"analysis_{ticker}.md"

    try:
        client.files_upload_v2(
            channel=channel,
            thread_ts=thread_ts,
            content=report,
            filename=filename,
            title=f"企業価値分析レポート: {ticker}",
            initial_comment=f"✅ *{ticker}* の分析が完了しました。",
        )
        logger.info(f"レポート送信完了: {ticker} (ファイルアップロード)")
    except Exception as e:
        logger.error(f"ファイルアップロード失敗: {e}。テキスト分割送信にフォールバック")
        _send_long_text(client, channel, thread_ts, report)


def _send_long_text(
    client: WebClient,
    channel: str,
    thread_ts: str,
    text: str,
) -> None:
    """3000文字ごとに分割してテキストメッセージとして送信するフォールバック"""
    CHUNK_SIZE = 3000
    chunks = []
    while len(text) > CHUNK_SIZE:
        split_point = text.rfind("\n", 0, CHUNK_SIZE)
        if split_point == -1:
            split_point = CHUNK_SIZE
        chunks.append(text[:split_point])
        text = text[split_point:].lstrip("\n")
    if text:
        chunks.append(text)

    for i, chunk in enumerate(chunks):
        client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=f"```{chunk}```" if i > 0 else chunk,
        )
    logger.info(f"テキスト分割送信完了: {len(chunks)} チャンク")
