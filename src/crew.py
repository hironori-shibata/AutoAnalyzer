"""
CrewAI Crew定義・分析オーケストレーター
run_analysis(ticker) がメインエントリーポイント。
- Phase 1: Agent1〜5を並列実行
- Phase 2: Agent6が全結果を集約してレポート生成
"""
import os
import json
import datetime
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


def _make_event_logger(event_log_path: str, crew_name: str):
    """
    CrewAI の step_callback / task_callback 用イベントロガーを返す。
    CrewAI Plus のテレメトリーに依存せず、ローカルの JSON Lines ファイルに
    イベントを書き出す。これにより「Unknown Crew / Running のまま」問題を回避する。
    """
    def _write(event: dict):
        event["crew"] = crew_name
        event["ts"] = datetime.datetime.now().isoformat()
        with open(event_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def step_callback(agent_output):
        """各Agentのアクション（ToolCallや思考）を記録する。"""
        try:
            entry = {
                "event": "step",
                "agent": getattr(agent_output, "agent", "unknown"),
                "output": str(agent_output)[:500],  # 先頭500文字のみ
            }
            _write(entry)
            logger.debug(f"[STEP] agent={entry['agent']}")
        except Exception:
            pass  # ログ失敗で分析を止めない

    def task_callback(task_output):
        """各Taskの完了を記録する。"""
        try:
            entry = {
                "event": "task_done",
                "task": getattr(task_output, "description", "")[:100],
                "summary": str(task_output)[:200],
            }
            _write(entry)
            logger.info(f"[TASK DONE] {entry['task']}")
        except Exception:
            pass

    return step_callback, task_callback


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
    log_dir = f"data/{ticker}"
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = f"{log_dir}/crew_execution.log"
    event_log_path = f"{log_dir}/crew_events.jsonl"

    crew_name = f"AutoAnalyzer_{ticker}"

    # CrewAI Plus テレメトリー（外部送信）は CREWAI_TELEMETRY_OPT_OUT=true で無効化推奨。
    # 代わりにローカルの event_log（JSONL形式）へ全イベントを記録する。
    step_cb, task_cb = _make_event_logger(event_log_path, crew_name)

    # 実行開始イベントを記録
    with open(event_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "event": "crew_start",
            "crew": crew_name,
            "ticker": ticker,
            "ts": datetime.datetime.now().isoformat(),
        }, ensure_ascii=False) + "\n")

    crew = Crew(
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
        step_callback=step_cb,
        task_callback=task_cb,
    )

    logger.info(f"Crew実行開始: {crew_name}")
    try:
        result = crew.kickoff()
        status = "completed"
    except Exception as e:
        status = f"failed: {e}"
        raise
    finally:
        # 正常終了・異常終了いずれの場合も終了イベントを記録する
        # （CrewAI Plus が "Running のまま" になる問題の代替記録）
        with open(event_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "event": "crew_end",
                "crew": crew_name,
                "ticker": ticker,
                "status": status,
                "ts": datetime.datetime.now().isoformat(),
            }, ensure_ascii=False) + "\n")
        logger.info(f"Crew実行終了: {crew_name} status={status}")

    # Step 5: レポート文字列を取得
    if hasattr(result, "raw"):
        report_text = result.raw
    else:
        report_text = str(result)

    # ヘッダーを付与
    report_text = add_report_header(report_text, ticker)
    logger.info(f"=== AutoAnalyzer 分析完了: {ticker} ===")
    return report_text
