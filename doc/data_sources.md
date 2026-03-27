# 外部データリソース設計書

## URL・取得方法一覧

### IR Bank

ベースURL: `https://irbank.net`

| データ種別 | URL パターン | 取得方法 | 使用Agent |
|---|---|---|---|
| 会社業績(EPS/ROE/ROA等 複数年) | `irbank.net/{EdinetCode}/results` | Jina Reader / BeautifulSoup | Agent1, Agent4 |
| 財務状況(複数年) | `irbank.net/{EdinetCode}/results` | 同上 | Agent4 |
| キャッシュフロー(複数年) | `irbank.net/{EdinetCode}/results` | 同上 | Agent4 |
| 配当(複数年) | `irbank.net/{EdinetCode}/results` | 同上 | Agent4 |
| 有報: リスク | `irbank.net/{EdinetCode}/risk?f={documentcode}` | Jina Reader | Agent1 |
| 有報: 課題 | `irbank.net/{EdinetCode}/task?f={documentcode}` | Jina Reader | Agent1 |
| 有報: 研究開発 | `irbank.net/{EdinetCode}/rd?f={documentcode}` | Jina Reader | Agent1 |
| 有報: 沿革 | `irbank.net/{EdinetCode}/history?f={documentcode}` | Jina Reader | Agent1 |
| 有報: 大株主 | `irbank.net/{EdinetCode}/notes/MajorShareholdersTextBlock?f={documentcode}` | Jina Reader | Agent1 |
| 有報: 連結会社・親会社 | `irbank.net/{EdinetCode}/af?f={documentcode}` | Jina Reader | Agent1 |
| 有報: 事業内容 | `irbank.net/{EdinetCode}/business?f={documentcode}` | Jina Reader | Agent1 |
| 有報: 設備状況 | `irbank.net/{EdinetCode}/facilities?f={documentcode}` | Jina Reader | Agent1 |
| 有報: 従業員状況 | `irbank.net/{EdinetCode}/notes/InformationAboutEmployeesTextBlock?f={documentcode}` | Jina Reader | Agent1 |
| 決算短信一覧 | `irbank.net/td/search?q={ticker}` | BeautifulSoup | Agent3 |
| 決算短信PDF | `f.irbank.net/{path}` | requests + docling | Agent3 |

> **EdinetCode** はローカルCSVから証券番号で引く（`src/utils/code_converter.py`）  
> **documentcode** はEdinet APIで取得する

---

### Edinet API

| エンドポイント | 用途 |
|---|---|
| `https://api.edinet-fsa.go.jp/api/v2/documents.json` | 書類一覧の取得（documentcode取得） |

```python
# documentcode取得イメージ
params = {
    "date": "2026-03-31",      # 決算期末 or 直近の提出日
    "type": 2,                  # 有価証券報告書
    "Subscription-Key": EDINET_API_KEY,
}
```

---

### 四季報 (東洋経済)

| データ種別 | URL | 取得方法 | 使用Agent |
|---|---|---|---|
| テーマ・セグメント・ライバル | `https://shikiho.toyokeizai.net/stocks/{ticker}` | Jina Reader | Agent2 |

---

### 株価・需給系サイト

| サイト | URL パターン | 取得データ | 使用Agent |
|---|---|---|---|
| 株探 | `https://kabutan.jp/stock/?code={ticker}` | 株価・出来高・PER・PBR等 | Agent2, Agent5 |
| 株探 信用残 | `https://kabutan.jp/stock/kabuka?code={ticker}` | 信用倍率・信用残 | Agent5 |
| 株予報pro | `https://kabuyoho.jp/reportTop?bcode={ticker}` | 業績予想・株価指標 | Agent5 |
| 空売り.net | `https://karauri.net/{ticker}/` | 空売り比率・残高 | Agent5 |
| IR Bank 株価 | `irbank.net/{EdinetCode}` | 株価・PER・PBR等 | Agent5 |

> **変更:** 四季報(shikiho.toyokeizai.net)はアクセス制御が厳しいため廃止済み。

### Web検索 (DuckDuckGO)

Agent2が競合情報・EV/EBITDAの個別調査（時価総額・純資産・有利子負債等）を行う際に使用。

| ポイント | 説明 |
|---|---|
| ツール | 独自 `WebSearchTool`（`duckduckgo_search` ライブラリ直接使用） |
| リージョン | `jp-jp`（日本に限定） |
| 中国語サイト除外 | `zhihu.com`, `baidu.com` 等のNGドメインを自動除外 |
| 取得件数 | `max_results * 2` を取得してフィルタ後に `max_results` 件返す |

---

## Jina Reader の使い方

スクレイピングが困難なページや、テキスト抽出を簡略化したい場合に使用。

```python
import requests
import time

def fetch_with_jina(url: str) -> str:
    """Jina Readerを通じてWebページをMarkdownで取得する"""
    jina_url = f"https://r.jina.ai/{url}"
    headers = {"User-Agent": "Mozilla/5.0"}
    time.sleep(1)  # 必須: 1秒待機
    res = requests.get(jina_url, headers=headers, timeout=30)
    res.raise_for_status()
    return res.text
```

---

## スクレイピング共通ルール

1. **すべてのHTTPリクエスト前に `time.sleep(1)` を必ず挿入すること**
2. User-Agentを必ず設定すること（`Mozilla/5.0`）
3. タイムアウトは30秒を基本とする
4. HTTPステータスコード != 200 の場合はリトライ最大3回
5. robots.txtを尊重し、禁止されているパスへのアクセスは行わないこと

```python
# スクレイピング共通テンプレート
import requests
import time
from loguru import logger

def safe_get(url: str, retries: int = 3) -> requests.Response | None:
    headers = {"User-Agent": "Mozilla/5.0"}
    for i in range(retries):
        try:
            time.sleep(1)  # 必須
            res = requests.get(url, headers=headers, timeout=30)
            res.raise_for_status()
            return res
        except Exception as e:
            logger.warning(f"Attempt {i+1} failed for {url}: {e}")
    logger.error(f"All retries failed for {url}")
    return None
```

---

## EdinetCode変換

`data/edinet_code_list.csv` (Edinet公式から取得・定期更新)を使用。

```python
import pandas as pd

def ticker_to_edinet_code(ticker: str) -> str | None:
    df = pd.read_csv("data/edinet_code_list.csv", encoding="cp932")
    row = df[df["証券コード"] == int(ticker)]
    if row.empty:
        return None
    return row.iloc[0]["ＥＤＩＮＥＴコード"]
```

> CSVの列名はEdinet公式フォーマットに準拠。エンコーディングはcp932に注意。
