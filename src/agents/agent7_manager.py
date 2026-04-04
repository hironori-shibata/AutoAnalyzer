"""
Agent7: 統括マネージャー（ボス）
全エージェントの出力を集約し、企業価値算定（DCF法・マルチプル法）を行い、
最終的な企業価値分析レポートを生成する。
計算はすべてPython Toolに委ねる。
"""
from crewai import Agent
from src.config import get_llm_long_output
from src.tools.valuation_calc import ReverseDCFTool, MultiplesValuationTool, ValuationComparisonTool, SOTPValuationTool
from src.tools.file_reader import MarkdownReadTool
from src.tools.kabutan_batch_tool import KabutanBatchTool


def create_agent7() -> Agent:
    return Agent(
        role="統括マネージャー・企業価値アナリスト",
        goal=(
            "各リサーチャーAgentの情報を統合し、DCF法・マルチプル法で企業価値を算定し、"
            "現在株価との乖離から投資判断サマリーを提供すること。"
            "すべての数値計算はPython Toolで行うこと。LLM自身は計算しない。"
        ),
        backstory=(
            "あなたは機関投資家レベルの企業価値分析の専門家です。"
            "定量・定性の両面から企業を評価し、DCFとマルチプルの2軸で株価の妥当性を判断します。"
            "業界構造の深い理解と、各Agentの情報を統合する総合的な視点が強みです。\n\n"
            "【絶対ルール】\n"
            "いかなる数値計算もLLM自身で行ってはならない。"
            "逆DCFの計算は必ず ReverseDCFTool を、マルチプルの計算は必ず MultiplesValuationTool を使うこと。"
        ),
        tools=[ReverseDCFTool(), MultiplesValuationTool(), ValuationComparisonTool(), SOTPValuationTool(), MarkdownReadTool(), KabutanBatchTool()],
        llm=get_llm_long_output(),  # 長文レポート出力用（max_tokens=8192）
        verbose=True,
        max_iter=35,
    )
