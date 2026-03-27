"""
IR Bank スクレイパー
IR BankのresultsページからEdinetCodeを使って業績データを取得する。
複数年の財務テーブルをMarkdown形式で返す。
"""
import time
from io import StringIO
from loguru import logger
from bs4 import BeautifulSoup
import pandas as pd
from crewai.tools import BaseTool
from pydantic import BaseModel

from src.tools.scraping_tools import safe_get
from src.config import IRBANK_BASE_URL


class IRBankScraperInput(BaseModel):
    edinet_code: str
    section: str = "results"  # results / risk / task / rd / business など


class IRBankScraperTool(BaseTool):
    """
    IR BankからEdinetCodeを使って業績データ・有報セクション情報を取得する。
    resultsページから複数年の財務データをテーブル形式でパースして返す。
    """
    name: str = "IRBankScraperTool"
    description: str = (
        "IR BankからEdinetCodeを使って業績データを取得する。"
        "section='results' で複数年の財務データ（売上・利益・ROE等）をMarkdownテーブルで返す。"
        "edinet_code: EdinetCode（E0XXXXX形式）を指定すること。"
    )
    args_schema: type[BaseModel] = IRBankScraperInput

    def _run(self, edinet_code: str, section: str = "results") -> str:
        url = f"{IRBANK_BASE_URL}/{edinet_code}/{section}"
        logger.info(f"IR Bank スクレイピング: {url}")

        res = safe_get(url)
        if not res:
            return f"ERROR: {url} の取得に失敗しました"

        soup = BeautifulSoup(res.text, "html.parser")
        tables = soup.find_all("table")

        if not tables:
            # テーブルが見つからない場合はページテキストを返す
            body_text = soup.get_text(separator="\n", strip=True)
            return body_text[:10000] if body_text else "テーブルデータが見つかりませんでした"

        results = []
        for i, table in enumerate(tables[:5]):  # 最大5テーブル
            try:
                dfs = pd.read_html(StringIO(str(table)))
                if dfs:
                    results.append(f"### テーブル {i + 1}\n\n{dfs[0].to_markdown(index=False)}\n")
            except Exception as e:
                logger.warning(f"テーブル {i + 1} のパース失敗: {e}")

        return "\n".join(results) if results else "データの取得・パースに失敗しました"
