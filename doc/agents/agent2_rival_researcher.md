# Agent2: ライバルリサーチャー 設計書

## 役割

対象企業の競合他社・業界構造を調査する。  
DuckDuckGO検索と株探スクレイピングを活用して競合指標（PER等）を取得し、業界比較分析を行う。

---

## 入力

| 項目 | 説明 |
|---|---|
| `ticker` | 4桁の証券番号 |
| `company_name` | 企業名（省略可） |

---

## 出力

以下の項目を含むMarkdownテキスト:

- 主要競合他社一覧（証券番号・企業名・特徴）
- 競合他社のPER・PBR等の主要指標（Agent6のマルチプル計算で使用）
- 業界ポジショニング（当該企業の強み・弱み）
- 最新の業界ニュース・動向（実行時点の最新年度）
- 5フォース分析の材料

---

## 取得するデータリソース

| データ | 取得先 | 取得方法 |
|---|---|---|
| 競合他社のPER・PBR等 | 株探: `kabutan.jp/stock/?code={ticker}` | StockScraperTool (source='kabutan_stock') |
| 業界動向・競合情報 | DuckDuckGO検索 | WebSearchTool |

> **変更:** 競合他社のEV/EBITDA調査は、データ取得の難易度が高く不正確になりやすいため廃止。
> LangChainの `DuckDuckGoSearchTool` から独自 `WebSearchTool` に変更。

---

## 使用するTool

| Tool名 | 説明 |
|---|---|
| `WebSearchTool` | `duckduckgo_search` ライブラリ直接使用の検索フラッパー。中国語サイト除外フィルタ付き |
| `StockScraperTool` | 株探・空売り.net・株予報proから指標を取得 |

---

## WebSearchToolの中国語除外フィルタ

「日本」「自動車」等の漢字クエリは知乎(zhihu.com)等の中国語サイトがヒットしやすい。  
このため `WebSearchTool` にはNGドメインフィルタを実装済み:

```python
ng_domains = ["zhihu.com", "baidu.com", "bilibili.com", "163.com", "qq.com", "weibo.com", "sohu.com"]
```

また、LLMには「単語の羅列ではなく、具体的な文章でクエリを作成すること」を強制する説明文を付与している。

---

## CrewAI Agent定義（実装済み）

```python
# src/agents/agent2_rival.py
from crewai import Agent
from src.config import get_llm
from src.tools.web_search import WebSearchTool
from src.tools.stock_scraper import StockScraperTool

def create_agent2() -> Agent:
    return Agent(
        role="ライバルリサーチャー",
        goal=(
            "対象企業の競合環境・業界構造を深く調査し、"
            "当該企業の競争優位性と脅威を明確にすること。"
        ),
        backstory=(
            "あなたは業界アナリストとして、競合比較と業界構造分析を専門としています。"
            "ウェブ検索や関連サイトの最新情報を最大限活用して、投資判断に必要な競争環境の全体像を描きます。"
        ),
        tools=[WebSearchTool(), StockScraperTool()],
        llm=get_llm(),
        verbose=True,
        max_iter=15,
    )
```

---

## CrewAI Task定義

```python
# src/tasks/task2_rival.py
from crewai import Task

def create_task2(ticker, company_name):
    return Task(
        description=(
            "証券番号 {ticker} の企業について、以下の競合調査を徹底的に実施してください:\n"
            "1. 対象企業の主要な競合他社（国内・海外問わず）を3〜5社程度特定\n"
            "2. 競合他社の証券番号（4桁）を特定し、StockScraperTool(source='kabutan_stock')で各社の詳細ページを取得し、PER、PBR、時価総額、利回り等の主要指標を抽出すること\n"
            "3. WebSearchToolを用いて、競合の最新動向や市場シェア、各社の強み・弱みを調べる\n"
            "4. {ticker}と競合他社の指標を比較し、相対的な投資魅力度を分析する\n"
            "⚠️ 情報が取得できない場合は「該当データなし」と記載してスキップして構いません。"
        ),
        expected_output=(
            "対象企業と競合他社を比較した詳細な競争環境レポート。\n"
            "各競合について、PER、PBR等の具体的数値を必ず記載すること。"
        ),
        agent=create_agent2(),
    )
```

---

## 注意事項

- DuckDuckGOは `jp-jp` リージョンで検索し、中国語サイトはNGドメインフィルタで自動除外
- EV/EBITDAが個別企業で見つからない場合は、必ず簡易計算式（EV = 時価総額 - 純資産 + 有利子負債）を用いて算出を試みること
- 競合他社の PER・EV/EBITDA はそのまま Agent6 の `MultiplesValuationTool` に入力される
