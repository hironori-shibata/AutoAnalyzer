"""
株探テーマ関連ツール（Agent2a: 競合銘柄コード補完用）

競合他社の証券番号がTask2から十分に得られなかった場合に、
株探のテーマページを経由して同業銘柄コードを自力で収集するためのツール群。

使用フロー:
  1. KabutanThemeListTool(ticker) → 対象企業が属するテーマ一覧とURLを取得
  2. エージェントが競合分析に有用なテーマURLを選定（LLMが吟味）
  3. KabutanThemeStocksTool(theme_url) → テーマに属する銘柄コード・銘柄名の一覧を取得
"""
from bs4 import BeautifulSoup
from crewai.tools import BaseTool
from pydantic import BaseModel
from loguru import logger

from src.tools.scraping_tools import safe_get

BASE_URL = "https://kabutan.jp"


# ===== KabutanThemeListTool =====

class ThemeListInput(BaseModel):
    ticker: str   # 4桁の証券番号（例: "7203"）


class KabutanThemeListTool(BaseTool):
    """
    指定した銘柄コードの株探ページから、その企業が属するテーマ一覧を取得する。
    各テーマの名称とテーマページURLのリストを返す。
    エージェントはこのリストを見て、競合分析に有用なテーマを選択してから
    KabutanThemeStocksTool に渡すこと。
    """
    name: str = "KabutanThemeListTool"
    description: str = (
        "指定した証券番号の株探ページから、その企業が属するテーマ一覧（テーマ名とURL）を取得する。\n"
        "ticker: 4桁の証券番号（例: '7203'）\n"
        "戻り値: [[テーマ名, テーマURL], ...] のリスト（URLは相対パス）\n"
        "⚠️ 取得したURLは BASE_URL='https://kabutan.jp' を先頭に付けてアクセスすること。\n"
        "【使用目的】競合銘柄コードが不足している場合に、関連テーマのURLを特定するために使う。\n"
        "取得したテーマ一覧から競合分析に有用なもの（業界・製品カテゴリ等）を選び、\n"
        "KabutanThemeStocksTool に渡して同業銘柄を収集すること。\n"
        "指数・地域・マクロ（例: TOPIX・円安・ESG）などは競合分析に不要なため選ばないこと。"
    )
    args_schema: type[BaseModel] = ThemeListInput

    def _run(self, ticker: str) -> list | str:
        url = f"{BASE_URL}/stock/?code={ticker}"
        res = safe_get(url)
        if res is None:
            return f"ERROR: {url} の取得に失敗しました"

        try:
            soup = BeautifulSoup(res.text, "html.parser")
            th = soup.find("th", string="テーマ")
            if not th:
                return f"ERROR: 銘柄コード {ticker} のページにテーマ情報が見つかりませんでした"

            td = th.find_next_sibling("td")
            if not td:
                return f"ERROR: テーマのtd要素が見つかりませんでした"

            result = []
            for a in td.find_all("a"):
                name = a.get_text(strip=True)
                href = a.get("href", "")
                if name and href:
                    result.append([name, href])

            if not result:
                return f"ERROR: テーマリンクが0件でした（{ticker}）"

            logger.info(f"KabutanThemeListTool: {ticker} のテーマ {len(result)} 件を取得")
            return result

        except Exception as e:
            return f"ERROR: パース失敗 ({e})"


# ===== KabutanThemeStocksTool =====

class ThemeStocksInput(BaseModel):
    theme_url: str   # テーマページのURL（BASE_URL付きフル URL、または相対パス）


class KabutanThemeStocksTool(BaseTool):
    """
    株探のテーマページURLから、そのテーマに属する銘柄コードと銘柄名の一覧を取得する。
    KabutanThemeListTool で得たURLを入力として使用する。
    """
    name: str = "KabutanThemeStocksTool"
    description: str = (
        "株探のテーマページから、テーマに属する銘柄コードと銘柄名の一覧を取得する。\n"
        "theme_url: テーマページのURL（例: 'https://kabutan.jp/themes/?theme=自動車' または "
        "'/themes/?theme=...' の相対パス）\n"
        "戻り値: [[銘柄コード, 銘柄名], ...] のリスト\n"
        "【使用目的】KabutanThemeListTool で選んだテーマURLに属する同業他社の銘柄コードを収集する。\n"
        "取得した銘柄コードから対象企業自身を除いた上で、競合候補として KabutanBatchTool に渡すこと。"
    )
    args_schema: type[BaseModel] = ThemeStocksInput

    def _run(self, theme_url: str) -> list | str:
        # 相対パスの場合はBASE_URLを補完する
        if theme_url.startswith("/"):
            url = BASE_URL + theme_url
        else:
            url = theme_url

        res = safe_get(url)
        if res is None:
            return f"ERROR: {url} の取得に失敗しました"

        try:
            soup = BeautifulSoup(res.text, "html.parser")
            table = soup.select_one("table.stock_table.st_market")

            if table is None:
                return f"ERROR: テーマページの銘柄テーブル（stock_table）が見つかりませんでした: {url}"

            result = []
            for row in table.find_all("tr"):
                tds = row.find_all("td")
                if len(tds) < 2:
                    continue
                code = tds[0].get_text(strip=True)
                name = tds[1].get_text(strip=True)
                if code and name:
                    result.append([code, name])

            if not result:
                return f"ERROR: 銘柄が0件でした（{url}）"

            logger.info(f"KabutanThemeStocksTool: {url} から銘柄 {len(result)} 件を取得")
            return result

        except Exception as e:
            return f"ERROR: パース失敗 ({e})"
