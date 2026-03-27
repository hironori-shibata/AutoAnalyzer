"""
DuckDuckGO 検索ラッパー
LangChain Community の DuckDuckGoSearchRun を CrewAI Tool として提供する。
Agent2 (ライバルリサーチャー) が使用する。
"""
from crewai.tools import BaseTool
from pydantic import BaseModel
from loguru import logger


class WebSearchInput(BaseModel):
    query: str
    max_results: int = 5


class WebSearchTool(BaseTool):
    """
    DuckDuckGOを使ってWeb検索を実行し、結果を返す。
    Agent2の競合・業界調査に使用する。
    """
    name: str = "DuckDuckGO Web検索ツール"
    description: str = (
        "DuckDuckGOを使ってWeb検索を実行し、関連する情報を返す。\n"
        "query: 検索クエリ文字列を渡すこと。\n"
        #"【注意】単なる単語の羅列（例: '日本 自動車メーカー'）だと無関係な海外サイトがヒットしやすいです。\n"
        "必ず具体的な文章や絞り込んだキーワード（例: 'トヨタ自動車 競合他社'）にしてください。"
    )
    args_schema: type[BaseModel] = WebSearchInput

    def _run(self, query: str, max_results: int = 5) -> str:
        try:
            from duckduckgo_search import DDGS
            logger.info(f"Web検索実行: {query}")
            
            # 検索言語/地域を日本・日本語に限定（region='jp-jp'）
            # 上位が中国語サイト等で埋まるのを防ぐため、多めに取得（max_resultsの10倍、最大50件）
            fetch_count = min(max_results * 10, 50)
            
            with DDGS() as ddgs:
                raw_results = list(ddgs.text(query, max_results=fetch_count, region='jp-jp',backend='lite'))
            
            if not raw_results:
                return "検索結果が見つかりませんでした。"
            
            # 中国語サイトや無関係なサイトのノイズを除外するためのNGドメインリスト
            ng_domains = ["zhihu.com", "baidu.com", "bilibili.com", "163.com", "qq.com", "weibo.com", "sohu.com"]
            
            formatted_results = []
            skipped_count = 0
            
            for r in raw_results:
                title = r.get('title', '')
                snippet = r.get('body', '')
                href = r.get('href', '')
                
                # NGドメインが含まれている場合はスキップ
                if any(domain in href for domain in ng_domains):
                    skipped_count += 1
                    continue
                    
                formatted_results.append(f"タイトル: {title}\n内容: {snippet}\nURL: {href}")
                if len(formatted_results) >= max_results:
                    break
            
            logger.info(f"DuckDuckGO 検索完了: ヒット={len(raw_results)}件, フィルタ除外={skipped_count}件, 採用={len(formatted_results)}件")
            
            if not formatted_results:
                return f"検索結果が見つかりませんでした（{len(raw_results)}件ヒットしましたが、すべて海外サイト等のノイズとして除外されました）。クエリをより具体的、または簡潔にして再試行してください。"
            
            return "\n\n".join(formatted_results)
        except ImportError:
            logger.error("duckduckgo-search がインストールされていません")
            return "ERROR: duckduckgo-search をインストールしてください"
        except Exception as e:
            logger.error(f"DuckDuckGO 検索エラー: {e}")
            return f"ERROR: 検索失敗: {e}"
