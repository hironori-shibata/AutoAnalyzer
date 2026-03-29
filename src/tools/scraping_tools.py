"""
Webスクレイピング共通ツール
- safe_get(): 全HTTPリクエスト共通関数（1秒sleep + リトライ）
- JinaReaderTool: Jina Reader APIでWebページをMarkdown取得
"""
import time
import requests
from loguru import logger
from crewai.tools import BaseTool
from pydantic import BaseModel

from src.config import (
    REQUEST_TIMEOUT,
    REQUEST_RETRIES,
    REQUEST_SLEEP,
    JINA_BASE_URL,
    JINA_MAX_CHARS,
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}


def safe_get(url: str, retries: int = REQUEST_RETRIES) -> requests.Response | None:
    """
    全ツール共通のHTTPリクエスト関数。
    ・すべてのリクエスト前に time.sleep(REQUEST_SLEEP) を挿入（設計書必須要件）
    ・失敗時はリトライ（最大 retries 回）
    """
    for i in range(retries):
        try:
            time.sleep(REQUEST_SLEEP)  # ★必須: 1秒以上のウェイト
            res = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            res.raise_for_status()
            return res
        except requests.exceptions.HTTPError as e:
            logger.warning(f"[Attempt {i + 1}/{retries}] HTTP Error {e.response.status_code}: {url}")
        except Exception as e:
            logger.warning(f"[Attempt {i + 1}/{retries}] {url}: {e}")
    logger.error(f"全リトライ失敗: {url}")
    return None


# ===== JinaReaderTool =====

class JinaReaderInput(BaseModel):
    url: str


class JinaReaderTool(BaseTool):
    """
    Webページを直接スクレイピングしてテキストを抽出するツール。
    （以前はJina Readerを使用していましたが、403エラー回避のため直接取得に変更）
    """
    name: str = "JinaReaderTool"
    description: str = (
        "指定URLのWebページからHTMLタグを除去したテキスト形式で内容を取得する。"
        "IR Bank・四季報・株探などのページ取得に使用。"
        "urlに完全なURLを渡すこと（https://から始まる）。"
    )
    args_schema: type[BaseModel] = JinaReaderInput

    def _run(self, url: str) -> str:
        res = safe_get(url)
        if res is None:
            return f"ERROR: {url} の取得に失敗しました"

        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(res.content, "html.parser")

            main = soup.find("main")
            target = main if main else soup

            # 不要なタグを除去
            for tag in target(["script", "style", "header", "footer", "nav"]):
                tag.decompose()

            text = target.get_text(separator="\n", strip=True)
            
            # 連続する改行を圧縮
            import re
            text = re.sub(r'\n+', '\n', text)

            if len(text) > JINA_MAX_CHARS:
                text = text[:JINA_MAX_CHARS]
                logger.info(f"レスポンスを {JINA_MAX_CHARS} 文字に切り詰め: {url}")
            return text
        except Exception as e:
            logger.error(f"HTMLパースエラー ({url}): {e}")
            return f"ERROR: パース失敗 ({e})"
