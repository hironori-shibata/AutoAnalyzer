"""
TradingViewEVEBITDATool: 複数の証券番号に対してTradingViewからEV/EBITDA倍率を一括取得するツール。

example3.py の実装を参考に CrewAI BaseTool として実装。
TradingView の財務指標ページをスクレイプし、EV/EBITDA を抽出して返す。
"""
import re
from typing import List
from pydantic import BaseModel
from crewai.tools import BaseTool
from loguru import logger

from src.tools.scraping_tools import safe_get

PER_TICKER_MAX_CHARS = 5000


def _scrape_tradingview_ev_ebitda(ticker: str) -> str:
    """
    TradingViewの財務指標ページからEV/EBITDAを抽出して返す。
    ticker: 4桁の証券番号（例: "7203"）
    """
    url = (
        f"https://jp.tradingview.com/symbols/TSE-{ticker}"
        f"/financials-statistics-and-ratios/"
        f"?selected=ev_ebitda%2Cprice_earnings%2Cprice_book_fwd"
    )
    res = safe_get(url)
    if res is None:
        return f"ERROR: {url} の取得に失敗しました"

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.text, "html.parser")

        # TradingViewの財務指標ページのメインコンテンツ
        main = soup.find("div", class_=re.compile(r"wrap-\w+ description-\w+"))
        if not main:
            # フォールバック: bodyから全テキストを取得
            main = soup.body

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


class TradingViewEVEBITDAInput(BaseModel):
    tickers: List[str]


class TradingViewEVEBITDATool(BaseTool):
    """
    TradingViewから複数銘柄のEV/EBITDA倍率を一括取得するツール。

    証券番号のリストを渡すと、各社のTradingView財務指標ページをスクレイプして結果を連結して返す。
    EV/EBITDAがマイナスの場合はTradingViewでは非表示になることがあるため、その旨も確認すること。
    """
    name: str = "TradingViewEVEBITDATool"
    description: str = (
        "複数の証券番号リストを受け取り、TradingViewから各社のEV/EBITDA倍率を一括取得する。"
        "tickers に4桁証券番号のリストを渡すこと（例: [\"7203\", \"7267\", \"7269\"]）。"
        "競合他社の証券番号が確定したら、このツールを1回呼び出すだけで全社分のEV/EBITDAが取得できる。"
        "EV/EBITDAがマイナスの場合はTradingViewに表示されないことがある。"
    )
    args_schema: type[BaseModel] = TradingViewEVEBITDAInput

    def _run(self, tickers: List[str]) -> str:
        results: list[str] = []

        for ticker in tickers:
            logger.info(f"TradingView EV/EBITDAスクレイピング: {ticker}")
            text = _scrape_tradingview_ev_ebitda(ticker)
            url = (
                f"https://jp.tradingview.com/symbols/TSE-{ticker}"
                f"/financials-statistics-and-ratios/"
            )
            results.append(
                f"## 証券番号: {ticker}\nURL: {url}\n\n{text}"
            )

        return "\n\n---\n\n".join(results)
