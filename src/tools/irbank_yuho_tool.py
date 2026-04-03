"""
IRBankYuhoTool: IR Bank から有価証券報告書の全定性情報を一括取得するツール。

9カテゴリのURLをループして順次スクレイプし、結果を1つのテキストとして返す。
LLMが個別URLを呼び出す必要がなくなり、ツール呼び出し回数を1回に削減できる。
"""
import re
from pydantic import BaseModel
from crewai.tools import BaseTool
from loguru import logger

from src.tools.scraping_tools import safe_get
from src.config import JINA_MAX_CHARS


CATEGORIES = [
    ("business",                                  "事業内容とセグメント構成"),
    ("risk",                                       "リスク情報（上位5件）"),
    ("task",                                       "経営課題"),
    ("rd",                                         "研究開発の状況"),
    ("notes/MajorShareholdersTextBlock",           "大株主構成（上位10位）"),
    ("af",                                         "親会社・連結会社の関係"),
    ("notes/InformationAboutEmployeesTextBlock",   "従業員状況（人数・平均年齢・平均年収）"),
    ("history",                                    "会社沿革のハイライト"),
    ("facilities",                                 "設備状況の概要"),
]

# 1カテゴリあたりの最大文字数（合計で JINA_MAX_CHARS 相当に収まるよう調整）
PER_CATEGORY_MAX_CHARS = 8000


def _scrape_irbank_page(url: str) -> str:
    """IR Bank の1ページをスクレイプしてテキストを返す。"""
    res = safe_get(url)
    if res is None:
        return f"ERROR: {url} の取得に失敗しました"

    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(res.content, "html.parser")

        # IR Bank は <div class="ccc"> がメインコンテンツ
        main = soup.find("div", class_="ccc")
        target = main if main else soup

        for tag in target(["script", "style", "header", "footer", "nav"]):
            tag.decompose()

        text = target.get_text(separator="\n", strip=True)
        text = re.sub(r'\n+', '\n', text)

        if len(text) > PER_CATEGORY_MAX_CHARS:
            text = text[:PER_CATEGORY_MAX_CHARS]
            logger.info(f"テキストを {PER_CATEGORY_MAX_CHARS} 文字に切り詰め: {url}")

        return text
    except Exception as e:
        logger.error(f"HTMLパースエラー ({url}): {e}")
        return f"ERROR: パース失敗 ({e})"


class IRBankYuhoInput(BaseModel):
    edinet_code: str
    document_code: str


class IRBankYuhoTool(BaseTool):
    """
    IR Bank から有価証券報告書の定性情報を一括取得するツール。

    edinet_code と document_code を渡すと、9カテゴリ（事業内容・リスク・経営課題・
    研究開発・大株主・関係会社・従業員・沿革・設備）のテキストを連結して返す。
    """
    name: str = "IRBankYuhoTool"
    description: str = (
        "IR Bank から有価証券報告書の全定性情報（事業内容・リスク・経営課題・研究開発・"
        "大株主・関係会社・従業員・沿革・設備）を一括取得する。"
        "edinet_code（例: E02144）と document_code（例: S100XXXX）を渡すこと。"
    )
    args_schema: type[BaseModel] = IRBankYuhoInput

    def _run(self, edinet_code: str, document_code: str) -> str:
        results: list[str] = []

        for category, description in CATEGORIES:
            url = f"https://irbank.net/{edinet_code}/{category}?f={document_code}"
            logger.info(f"取得中: {description} ({url})")
            text = _scrape_irbank_page(url)
            results.append(f"## {description}\nURL: {url}\n\n{text}")

        return "\n\n---\n\n".join(results)
