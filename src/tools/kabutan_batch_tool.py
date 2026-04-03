"""
KabutanBatchTool: 複数の証券番号に対して株探から定量データを一括取得するツール。

証券番号リストをループして順次スクレイプし、結果を1つのテキストとして返す。
LLMが個別に StockScraperTool を呼び出す必要がなくなり、ツール呼び出し回数を1回に削減できる。
"""
import re
from typing import List
from pydantic import BaseModel
from crewai.tools import BaseTool
from loguru import logger

from src.tools.scraping_tools import safe_get

# 1社あたりの最大文字数
PER_TICKER_MAX_CHARS = 5000


def _scrape_kabutan_stock(ticker: str) -> str:
    """株探の株価基本情報ページをスクレイプしてテキストを返す。"""
    url = f"https://kabutan.jp/stock/?code={ticker}"
    res = safe_get(url)
    if res is None:
        return f"ERROR: {url} の取得に失敗しました"

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, "html.parser")

        # 株価基本情報は div#stockinfo_i0 がメインコンテンツ（example2.py 参照）
        main = soup.select_one("div#stockinfo_i0")
        if not main:
            # フォールバック: div#main 全体を使用
            main = soup.find("div", id="main")
        target = main if main else soup

        for tag in target(["script", "style", "header", "footer", "nav"]):
            tag.decompose()

        text = target.get_text(separator="\n", strip=True)
        text = re.sub(r'\n+', '\n', text)

        if len(text) > PER_TICKER_MAX_CHARS:
            text = text[:PER_TICKER_MAX_CHARS]
            logger.info(f"テキストを {PER_TICKER_MAX_CHARS} 文字に切り詰め: {url}")

        return text
    except Exception as e:
        logger.error(f"HTMLパースエラー ({url}): {e}")
        return f"ERROR: パース失敗 ({e})"


class KabutanBatchInput(BaseModel):
    tickers: List[str]


class KabutanBatchTool(BaseTool):
    """
    株探から複数銘柄の定量データ（PER・PBR・時価総額・配当利回り）を一括取得するツール。

    証券番号のリストを渡すと、各社の株探ページをスクレイプして結果を連結して返す。
    """
    name: str = "KabutanBatchTool"
    description: str = (
        "複数の証券番号リストを受け取り、株探から各社のPER・PBR・時価総額・配当利回りを一括取得する。"
        "tickers に4桁証券番号のリストを渡すこと（例: [\"7203\", \"7267\", \"7269\"]）。"
        "競合他社の証券番号が確定したら、このツールを1回呼び出すだけで全社のデータが取得できる。"
    )
    args_schema: type[BaseModel] = KabutanBatchInput

    def _run(self, tickers: List[str]) -> str:
        results: list[str] = []

        for ticker in tickers:
            logger.info(f"株探スクレイピング: {ticker}")
            text = _scrape_kabutan_stock(ticker)
            results.append(f"## 証券番号: {ticker}\nURL: https://kabutan.jp/stock/?code={ticker}\n\n{text}")

        return "\n\n---\n\n".join(results)
