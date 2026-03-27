# Webスクレイピングツール仕様書

## 基本ルール（全ツール共通）

> ⚠️ **すべてのHTTPリクエストの前に `time.sleep(1)` を挿入すること**

```python
import time, requests
from loguru import logger

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def safe_get(url: str, retries: int = 3) -> requests.Response | None:
    for i in range(retries):
        try:
            time.sleep(1)  # 必須: 1秒ウェイト
            res = requests.get(url, headers=HEADERS, timeout=30)
            res.raise_for_status()
            return res
        except Exception as e:
            logger.warning(f"[Attempt {i+1}] {url}: {e}")
    return None
```

---

## `JinaReaderTool`

**ファイル**: `src/tools/scraping_tools.py`

Jina Reader APIを使ってWebページをMarkdown形式で取得する。  
JavaScriptヘビーなページや、HTMLパースが複雑なページに使用する。

```python
class JinaReaderInput(BaseModel):
    url: str

class JinaReaderTool(BaseTool):
    name: str = "Jina Reader ウェブ取得ツール"
    description: str = (
        "指定URLのWebページをJina Reader経由でMarkdown形式で取得する。"
        "IR Bank・四季報・株探などのページ取得に使用。"
    )
    args_schema = JinaReaderInput

    def _run(self, url: str) -> str:
        jina_url = f"https://r.jina.ai/{url}"
        res = safe_get(jina_url)
        if res is None:
            return f"ERROR: {url} の取得に失敗しました"
        return res.text[:50000]  # 長すぎる場合は先頭50,000文字に制限
```

---

## `KessanFetcherTool`

**ファイル**: `src/tools/kessan_fetcher.py`  
**使用Agent**: Agent3

決算短信の取得からPDF変換まで一連の処理を担当。

```python
class KessanFetcherTool(BaseTool):
    name: str = "決算短信取得・変換ツール"
    description: str = (
        "IR BankからティッカーをもとにPDF形式の決算短信を取得し、"
        "doclingを使ってMarkdownに変換して返す。"
    )

    def _run(self, ticker: str) -> str:
        # Step 1: 決算短信ページURLを取得
        search_url = f"https://irbank.net/td/search?q={ticker}"
        res = safe_get(search_url)
        if not res:
            return "ERROR: 決算短信検索ページの取得に失敗"

        soup = BeautifulSoup(res.text, "html.parser")
        kessan_url = None
        for a in soup.find_all("a"):
            if a.text and "期決算短信" in a.text:
                href = a.get("href", "")
                kessan_url = f"https://irbank.net{href}" if href.startswith("/") else href
                break

        if not kessan_url:
            return "ERROR: 決算短信リンクが見つかりませんでした"

        # Step 2: PDFリンクを取得
        time.sleep(1)
        res2 = safe_get(kessan_url)
        if not res2:
            return "ERROR: 決算短信詳細ページの取得に失敗"

        soup2 = BeautifulSoup(res2.text, "html.parser")
        pdf_url = None
        for a in soup2.find_all("a"):
            if a.text and "PDF" in a.text:
                href = a.get("href", "")
                pdf_url = f"https://f.irbank.net{href}" if href.startswith("/") else href
                break

        if not pdf_url:
            return "ERROR: PDFリンクが見つかりませんでした"

        # Step 3: doclingでPDF → Markdown変換
        return self._convert_pdf(pdf_url)

    def _convert_pdf(self, pdf_url: str) -> str:
        from docling.document_converter import DocumentConverter
        try:
            time.sleep(1)
            converter = DocumentConverter()
            result = converter.convert(pdf_url)
            md = result.document.export_to_markdown()
            # data/{ticker}/ に保存する処理は呼び出し元で行う
            return md
        except Exception as e:
            logger.error(f"PDF変換失敗: {e}")
            return f"ERROR: PDF変換に失敗しました: {e}"
```

---

## `IRBankScraperTool`

**ファイル**: `src/tools/irbank_scraper.py`  
**使用Agent**: Agent4

IR Bankのresultsページから複数年業績テーブルをパースしてJSON形式で返す。

```python
class IRBankScraperInput(BaseModel):
    edinet_code: str
    section: str = "results"  # results / risk / task など

class IRBankScraperTool(BaseTool):
    name: str = "IR Bank スクレイパー"
    description: str = (
        "IR BankからEdinetCodeを使って業績データ・有報セクション情報を取得する。"
        "resultsページから複数年の財務データをテーブル形式でパースして返す。"
    )
    args_schema = IRBankScraperInput

    def _run(self, edinet_code: str, section: str = "results") -> str:
        url = f"https://irbank.net/{edinet_code}/{section}"
        res = safe_get(url)
        if not res:
            return f"ERROR: {url} の取得に失敗"

        soup = BeautifulSoup(res.text, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            return "テーブルデータが見つかりませんでした"

        # pandasでテーブルをパース
        import pandas as pd
        from io import StringIO
        dfs = pd.read_html(StringIO(str(tables[0])))
        return dfs[0].to_markdown(index=False) if dfs else "データなし"
```

---

## `StockScraperTool`

**ファイル**: `src/tools/stock_scraper.py`  
**使用Agent**: Agent5

株探・空売り.netから需給データをスクレイピングする。

```python
class StockScraperInput(BaseModel):
    ticker: str
    source: str  # "kabutan_margin" | "karauri" | "kabutan_stock" | "kabuyoho"

class StockScraperTool(BaseTool):
    name: str = "株価・需給スクレイパー"
    description: str = (
        "株探・空売り.net・株予報proから信用倍率・空売り比率などの需給データを取得する。"
        "sourceに取得先サイトを指定すること。"
    )
    args_schema = StockScraperInput

    SOURCE_URLS = {
        "kabutan_stock":  "https://kabutan.jp/stock/?code={ticker}",
        "kabutan_margin": "https://kabutan.jp/stock/margin?code={ticker}",
        "karauri":        "https://karauri.net/{ticker}/",
        "kabuyoho":       "https://kabuyoho.jp/reportTop?bcode={ticker}",
    }

    def _run(self, ticker: str, source: str) -> str:
        url_template = self.SOURCE_URLS.get(source)
        if not url_template:
            return f"ERROR: 不明なsource: {source}"

        url = url_template.format(ticker=ticker)

        # 株探はJina Reader経由の方が安定
        if source.startswith("kabutan"):
            jina_url = f"https://r.jina.ai/{url}"
            res = safe_get(jina_url)
        else:
            res = safe_get(url)

        if not res:
            return f"ERROR: {url} の取得に失敗"

        # テーブルパース（空売り.netはBeautifulSoup）
        if source == "karauri":
            return self._parse_karauri(res.text)

        return res.text[:30000]

    def _parse_karauri(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")
        tables = soup.find_all("table")
        if not tables:
            return "テーブルなし"
        import pandas as pd
        from io import StringIO
        dfs = pd.read_html(StringIO(str(tables[0])))
        return dfs[0].to_markdown(index=False) if dfs else "データなし"
```

---

## `EdinetClientTool`

**ファイル**: `src/tools/edinet_client.py`  
**使用**: オーケストレーター（`crew.py`）

```python
import os, requests, time

def get_document_code(edinet_code: str, doc_type: int = 120) -> str | None:
    """
    Edinet APIから最新の有価証券報告書のdocumentcodeを取得する。
    doc_type: 120 = 有価証券報告書
    """
    from datetime import date, timedelta
    api_key = os.environ["EDINET_API_KEY"]
    # 直近365日を遡って書類を探す
    for days_ago in range(0, 365, 7):
        target_date = (date.today() - timedelta(days=days_ago)).strftime("%Y-%m-%d")
        url = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
        params = {"date": target_date, "type": 2, "Subscription-Key": api_key}
        time.sleep(1)
        res = requests.get(url, params=params, timeout=30)
        if res.status_code != 200:
            continue
        for doc in res.json().get("results", []):
            if doc.get("edinetCode") == edinet_code and doc.get("docTypeCode") == str(doc_type):
                return doc.get("docID")
    return None
```
