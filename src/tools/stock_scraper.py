"""
株価・需給スクレイパー
株探・空売り.net・株予報proから信用倍率・空売り比率などの需給データを取得する。
"""
from io import StringIO
from loguru import logger
from bs4 import BeautifulSoup
import pandas as pd
from crewai.tools import BaseTool
from pydantic import BaseModel

from src.tools.scraping_tools import safe_get
from src.config import JINA_BASE_URL


class StockScraperInput(BaseModel):
    ticker: str
    source: str  # "kabutan_stock" | "kabutan_margin" | "karauri" | "kabuyoho"


class StockScraperTool(BaseTool):
    """
    株探・空売り.net・株予報proから信用倍率・空売り比率などの需給データを取得する。
    sourceに取得先サイトを指定すること。

    source の選択肢:
      - "kabutan_stock"  : 株探・株価基本情報（PER/PBR/出来高等）
      - "kabutan_margin" : 株探・信用残（信用倍率・買い売り残の週次推移）
      - "karauri"        : 空売り.net（空売り比率・残高の日次推移）
      - "kabuyoho"       : 株予報pro（業績予想・テクニカル情報）
    """
    name: str = "StockScraperTool"
    description: str = (
        "株探・空売り.net・株予報proから信用倍率・空売り比率などの需給データを取得する。"
        "ticker: 4桁証券番号, source: 'kabutan_stock'|'kabutan_margin'|'karauri'|'kabuyoho' を指定。"
    )
    args_schema: type[BaseModel] = StockScraperInput

    SOURCE_URLS: dict = {
        "kabutan_stock":  "https://kabutan.jp/stock/?code={ticker}",
        "kabutan_margin": "https://kabutan.jp/stock/kabuka?code={ticker}",
        "karauri":        "https://karauri.net/{ticker}/",
        "kabuyoho":       "https://kabuyoho.jp/reportTop?bcode={ticker}",
    }

    def _run(self, ticker: str, source: str) -> str:
        url_template = self.SOURCE_URLS.get(source)
        if not url_template:
            return f"ERROR: 不明なsource: {source}。使用可能: {list(self.SOURCE_URLS.keys())}"

        url = url_template.format(ticker=ticker)
        logger.info(f"需給スクレイピング [{source}]: {url}")

        # 全ソース統一: 直接スクレイピング（Jina Reader URL経由はブロックされるため廃止）
        res = safe_get(url)

        if not res:
            return f"ERROR: {url} の取得に失敗しました"

        # 空売り.netはBeautifulSoupでテーブルをパース
        if source == "karauri":
            return self._parse_karauri(res.content)

        # 株探・株予報proはBeautifulSoupでテキスト抽出
        try:
            from bs4 import BeautifulSoup
            import re
            soup = BeautifulSoup(res.content, "html.parser")
            # kabutan は div#main 内のコンテンツのみ取得
            if source in ("kabutan_stock", "kabutan_margin"):
                main_div = soup.find("div", id="main")
                soup = main_div if main_div else soup
            for tag in soup(["script", "style", "nav", "header", "footer"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            text = re.sub(r'\n+', '\n', text)
            return text[:30000]
        except Exception as e:
            logger.warning(f"HTMLパース失敗 ({source}), テキストで返します: {e}")
            return res.text[:30000]

    def _parse_karauri(self, html: str) -> str:
        """空売り.netのHTMLからテーブルをパースしてMarkdownで返す"""
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            # テーブルがなければテキスト
            return soup.get_text(separator="\n", strip=True)[:10000]

        results = []
        for i, table in enumerate(tables[:3]):
            try:
                dfs = pd.read_html(StringIO(str(table)))
                if dfs:
                    results.append(f"### テーブル {i + 1}\n\n{dfs[0].to_markdown(index=False)}\n")
            except Exception as e:
                logger.warning(f"karauri テーブル {i + 1} パース失敗: {e}")

        return "\n".join(results) if results else "テーブルデータが見つかりませんでした"
