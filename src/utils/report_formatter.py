"""
レポートフォーマット整形ユーティリティ
最終レポートのヘッダー付与・文字数チェック等を行う
"""
from datetime import datetime, timezone, timedelta


JST = timezone(timedelta(hours=9))


def add_report_header(report: str, ticker: str, company_name: str = "") -> str:
    """
    レポートに生成日時・証券番号ヘッダーを付与する。
    既にヘッダーが付いている場合はそのまま返す。
    """
    if report.startswith("# 企業価値分析レポート"):
        return report

    now = datetime.now(JST).strftime("%Y-%m-%d %H:%M")
    title = f"# 企業価値分析レポート: {company_name} ({ticker})" if company_name else f"# 企業価値分析レポート: ({ticker})"
    header = f"{title}\n生成日時: {now}\n\n"
    return header + report


def truncate_for_slack(text: str, max_chars: int = 3900) -> list[str]:
    """
    Slackメッセージの文字数制限（4000文字）に合わせてテキストを分割する。
    """
    chunks = []
    while len(text) > max_chars:
        # 改行で区切れる場所を探す
        split_point = text.rfind("\n", 0, max_chars)
        if split_point == -1:
            split_point = max_chars
        chunks.append(text[:split_point])
        text = text[split_point:].lstrip("\n")
    if text:
        chunks.append(text)
    return chunks
