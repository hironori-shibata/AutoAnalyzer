"""
Agent2a: 競合データ収集エージェント
競合他社の証券番号を特定し、StockScraperToolで定量データを収集する。
DeepSeek v3 を使用（function calling が安定しているため）。
"""
from crewai import Agent
from src.config import get_llm
from src.tools.kabutan_batch_tool import KabutanBatchTool
from src.tools.tradingview_ev_ebitda_tool import TradingViewEVEBITDATool


def create_agent2a() -> Agent:
    llm = get_llm()
    return Agent(
        role="競合データ収集エージェント",
        goal=(
            "対象企業の主要競合他社（5〜7社）を特定し、"
            "KabutanBatchToolで各社のPER・PBR・時価総額・配当利回りを、"
            "TradingViewEVEBITDAToolでEV/EBITDA倍率を一括収集すること。"
        ),
        backstory=(
            "あなたは定量データ収集のスペシャリストです。"
            "競合他社の証券番号を調べ、株探とTradingViewから財務指標を確実に取得します。"
            "数値の正確性を最優先し、取得できないデータは正直に「該当データなし」と記載します。"
        ),
        tools=[KabutanBatchTool(), TradingViewEVEBITDATool()],
        llm=llm,
        verbose=True,
        max_iter=5,
    )
