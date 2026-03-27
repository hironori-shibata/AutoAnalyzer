"""
決算短信取得・PDF変換ツール
IR BankのtdnetページからPDF形式の決算短信を取得し、
doclingを使ってMarkdownに変換して返す。
"""
import os
import re
import time
from bs4 import BeautifulSoup
from loguru import logger
from crewai.tools import BaseTool
from pydantic import BaseModel

from src.tools.scraping_tools import safe_get
from src.config import PDF_CONVERT_TIMEOUT


class KessanFetcherInput(BaseModel):
    ticker: str


class KessanFetcherTool(BaseTool):
    """
    IR BankのtdnetページからPDF形式の最新決算短信を取得し、
    doclingを使ってMarkdownに変換して返す。

    処理フロー:
      1. irbank.net/{ticker}/ir で決算一覧（tdnet）を確認
      2. 「決算短信」を含む最新の開示リンクを探す
      3. 詳細ページから「PDFをみる」リンクを取得
      4. doclingでPDF → Markdown変換
    """
    name: str = "KessanFetcherTool"
    description: str = (
        "IR BankからティッカーをもとにPDF形式の最新決算短信を取得し、"
        "doclingを使ってMarkdownに変換して返す。"
        "ticker: 4桁の証券番号を文字列で渡すこと。"
    )
    args_schema: type[BaseModel] = KessanFetcherInput

    def _run(self, ticker: str) -> str:
        # Step 1: IR BankのIR一覧ページを取得
        ir_url = f"https://irbank.net/{ticker}/ir"
        logger.info(f"IR一覧ページ取得: {ir_url}")
        res = safe_get(ir_url)
        if not res:
            return "ERROR: IR一覧ページの取得に失敗しました"

        soup = BeautifulSoup(res.content, "html.parser")

        # Step 2: 「決算短信」を含む最新リンクを探す（プレゼンや補足資料は除外）
        detail_url = None
        for a in soup.find_all("a"):
            text = a.get_text(strip=True)
            href = a.get("href", "")
            if text and ("決算短信" in text) and ("プレゼン" not in text) and ("補足" not in text) and href:
                if href.startswith("/"):
                    detail_url = f"https://irbank.net{href}"
                elif href.startswith("http"):
                    detail_url = href
                logger.info(f"決算短信リンク検出: {text} → {detail_url}")
                break

        if not detail_url:
            logger.warning("決算短信リンクが見つからないため tdnet ページで再試行")
            # フォールバック: EdinetCodeなしでtdnetを試みる
            tdnet_url = f"https://irbank.net/td/search?q={ticker}"
            res2 = safe_get(tdnet_url)
            if res2:
                soup2 = BeautifulSoup(res2.content, "html.parser")
                for a in soup2.find_all("a"):
                    text = a.get_text(strip=True)
                    href = a.get("href", "")
                    if text and "決算短信" in text and href:
                        if not href.startswith("http"):
                            detail_url = f"https://irbank.net{href}"
                        else:
                            detail_url = href
                        logger.info(f"[フォールバック] 決算短信リンク: {text} → {detail_url}")
                        break

        if not detail_url:
            return "ERROR: 決算短信リンクが見つかりませんでした"

        # Step 3: 詳細ページから「PDFをみる」リンクを取得
        res3 = safe_get(detail_url)
        if not res3:
            return "ERROR: 決算短信詳細ページの取得に失敗しました"

        soup3 = BeautifulSoup(res3.content, "html.parser")
        pdf_url = None
        for a in soup3.find_all("a"):
            text = a.get_text(strip=True)
            href = a.get("href", "")
            if href and ".pdf" in href.lower():
                if href.startswith("http"):
                    pdf_url = href
                elif href.startswith("/"):
                    pdf_url = f"https://f.irbank.net{href}"
                else:
                    pdf_url = f"https://f.irbank.net/{href}"
                logger.info(f"PDFリンク検出: {pdf_url}")
                break

        if not pdf_url:
            return "ERROR: PDFリンクが見つかりませんでした"

        # Step 4: doclingでPDF → Markdown変換
        return self._convert_pdf_to_markdown(pdf_url, ticker)

    def _convert_pdf_to_markdown(self, pdf_url: str, ticker: str) -> str:
        """doclingを使ってPDFをMarkdownに変換し、data/{ticker}/に保存する"""
        try:
            from docling.document_converter import DocumentConverter

            logger.info(f"docling PDF変換開始: {pdf_url}")
            time.sleep(1)  # 礼儀としてのsleep

            converter = DocumentConverter()
            result = converter.convert(pdf_url)
            md = result.document.export_to_markdown()

            # data/{ticker}/ に保存
            save_dir = f"data/{ticker}"
            os.makedirs(save_dir, exist_ok=True)
            save_path = os.path.join(save_dir, "kessan_tansin.md")
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(md)
            logger.info(f"決算短信Markdown保存: {save_path}")

            return md

        except ImportError:
            logger.error("docling がインストールされていません: pip install docling")
            return "ERROR: docling がインストールされていません"
        except Exception as e:
            logger.error(f"PDF変換失敗: {e}")
            return f"ERROR: PDF変換に失敗しました: {e}"
