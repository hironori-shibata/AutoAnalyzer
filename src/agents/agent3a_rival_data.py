"""
Agent3a: 競合データ収集エージェント
競合他社の証券番号を特定し、StockScraperToolで定量データを収集する。
DeepSeek v3 を使用（function calling が安定しているため）。
"""
from crewai import Agent
from src.config import get_llm
from src.tools.kabutan_batch_tool import KabutanBatchTool
from src.tools.tradingview_ev_ebitda_tool import TradingViewEVEBITDATool
from src.tools.kabutan_theme_tools import KabutanThemeListTool, KabutanThemeStocksTool


def create_agent3a() -> Agent:
    llm = get_llm()
    return Agent(
        role="競合データ収集エージェント",
        goal=(
            "対象企業のセグメント数Nを確認し、N=1なら5〜7社・N=2なら6〜8社・N≥3ならN×3社を目標に競合他社を特定すること。"
            "KabutanBatchToolで各社のPER・PBR・時価総額・配当利回りを、"
            "TradingViewEVEBITDAToolでEV/EBITDA倍率を一括収集すること。"
            "競合銘柄コードが不足する場合は、KabutanThemeListTool と KabutanThemeStocksTool を使って"
            "株探のテーマページから同業銘柄を自力で補完すること。"
            "N≥2の場合は各セグメントに最低3社を割り当ててセグメント別PERテーブルを作成すること。"
        ),
        backstory=(
            "あなたは定量データ収集のスペシャリストです。"
            "競合他社の証券番号を調べ、株探とTradingViewから財務指標を確実に取得します。"
            "Task2から証券番号が十分に得られない場合は、株探のテーマ機能を活用して"
            "同業他社の銘柄コードを自力で探し出します。"
            "数値の正確性を最優先し、取得できないデータは正直に「該当データなし」と記載します。"
        ),
        tools=[
            KabutanBatchTool(),
            TradingViewEVEBITDATool(),
            KabutanThemeListTool(),
            KabutanThemeStocksTool(),
        ],
        llm=llm,
        verbose=True,
        max_iter=8,
    )
