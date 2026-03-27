"""
CrewAI Crew定義・分析オーケストレーター
run_analysis(ticker) がメインエントリーポイント。
- Phase 1: Agent1〜5を並列実行
- Phase 2: Agent6が全結果を集約してレポート生成
"""
import os
from loguru import logger
from crewai import Crew, Process

from src.utils.code_converter import ticker_to_edinet_code
from src.tools.edinet_client import get_document_code
from src.utils.report_formatter import add_report_header

from src.tasks.task1_yuho import create_task1
from src.tasks.task2_rival import create_task2
from src.tasks.task3_kessan import create_task3
from src.tasks.task4_performance import create_task4
from src.tasks.task5_stock import create_task5
from src.tasks.task6_report import create_task6


def run_analysis(ticker: str) -> str:
    """
    証券番号を受け取り、6 Agentが協調して企業価値分析レポートを生成して返す。

    Args:
        ticker: 4桁の証券番号（例: "7203"）

    Returns:
        Markdown形式の企業価値分析レポート文字列
    """
    logger.info(f"=== AutoAnalyzer 分析開始: {ticker} ===")

    # Step 1: EdinetCode変換
    edinet_code = ticker_to_edinet_code(ticker)
    if not edinet_code:
        raise ValueError(
            f"証券番号 {ticker} のEdinetCodeが見つかりませんでした。"
            "data/edinet_code_list.csv が正しく配置されているか確認してください。"
        )
    logger.info(f"EdinetCode: {edinet_code}")

    # Step 2: documentcode取得
    document_code = get_document_code(edinet_code)
    if not document_code:
        logger.warning(f"documentcodeが取得できませんでした ({edinet_code})。有報リサーチをスキップします。")
        document_code = "NOT_FOUND"

    logger.info(f"documentcode: {document_code}")

    # Step 3: タスク生成
    task1 = create_task1(ticker, edinet_code, document_code)
    task2 = create_task2(ticker)
    task3 = create_task3(ticker)
    task4 = create_task4(ticker, edinet_code)
    task5 = create_task5(ticker, edinet_code)
    task6 = create_task6(ticker, task1, task2, task3, task4, task5)

    # Step 4: Crew構築・実行
    # Agent1〜5: 並列実行 (sequential だが CrewAI の context 機能で Agent6 が全結果を参照)
    # Agent6: context=[task1..task5] により全結果を受け取って最後に実行
    # 実行ログファイルのパスを作成
    log_dir = f"data/{ticker}"
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = f"{log_dir}/crew_execution.log"

    crew = Crew(
        name=f"AutoAnalyzer_{ticker}",
        agents=[
            task1.agent,
            task2.agent,
            task3.agent,
            task4.agent,
            task5.agent,
            task6.agent,
        ],
        tasks=[task1, task2, task3, task4, task5, task6],
        process=Process.sequential,  # task6 が context で 1〜5 を参照するため sequential
        verbose=True,
        output_log_file=log_file_path,
    )

    logger.info("Crew実行開始...")
    result = crew.kickoff()
    logger.info("Crew実行完了")

    # Step 5: レポート文字列を取得
    if hasattr(result, "raw"):
        report_text = result.raw
    else:
        report_text = str(result)

    # ヘッダーを付与
    report_text = add_report_header(report_text, ticker)
    logger.info(f"=== AutoAnalyzer 分析完了: {ticker} ===")
    return report_text
