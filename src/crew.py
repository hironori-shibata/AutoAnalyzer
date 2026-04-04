"""
CrewAI Crew定義・分析オーケストレーター
run_analysis(ticker) がメインエントリーポイント。
- Phase 1: Task1〜Task6を順次実行
- Phase 2: Agent7が全結果を集約してレポート生成
- Phase 3: Agent8（批評）→ Agent9（最終投資判断）
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
from src.tasks.task2_gemini import create_task2
from src.tasks.task3_rival import create_task3
from src.tasks.task3a_rival_data import create_task3a
from src.tasks.task3b_rival_report import create_task3b
from src.tasks.task4_kessan import create_task4
from src.tasks.task5_performance import create_task5
from src.tasks.task6_news import create_task6
from src.tasks.task7_report import create_task7
from src.tasks.task8_critic import create_task8
from src.tasks.task9_investor import create_task9


def _make_event_logger(
    event_log_path: str,
    crew_name: str,
    tasks: list,
    slack_client=None,
    slack_channel: str = "",
    slack_thread_ts: str = "",
):
    """
    CrewAI の step_callback / task_callback 用イベントロガーを返す。
    ローカルの JSON Lines ファイルに全イベントを完全記録する。

    改善点:
      - Agent1〜6 の識別: sequential 実行順とタスク完了カウンターで自動ラベル付け
      - 全フィールド完全出力: model_dump() → vars() → 個別属性の3段階抽出で切り捨てなし
      - AgentAction / ToolResult それぞれの正しい属性名に対応
    """
    # sequential 実行で「現在何番目のタスクを実行中か」を追跡する共有状態。
    # task_callback が発火するたびに task_idx を +1 する。
    # step イベントには task_idx から導出した agent_num / agent_role を付与する。
    _state: dict = {"task_idx": 0}
    _agent_labels: list[str] = [
        f"Agent{i + 1}({getattr(t.agent, 'role', f'task{i+1}')})"
        for i, t in enumerate(tasks)
    ]

    def _write(event: dict) -> None:
        event["crew"] = crew_name
        event["ts"] = datetime.datetime.now().isoformat()
        with open(event_log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

    def _safe_val(v):
        """JSON 直列化できる型に変換する（失敗したら str）。"""
        if isinstance(v, (str, int, float, bool, type(None))):
            return v
        if isinstance(v, (dict, list)):
            return v
        return str(v)

    def _extract_step_details(agent_output) -> dict:
        """
        CrewAI 1.x の step_callback オブジェクトから全フィールドを抽出する。

        抽出戦略（順番に試す）:
          1. model_dump()  — Pydantic v2 モデル（CrewAI 1.x の主要型）
          2. dict(obj)     — Pydantic v1 / __iter__ 対応型
          3. vars(obj)     — 通常の Python クラス
          4. 個別属性リスト — 上記3種で取れなかったフィールドを補完

        AgentAction フィールド: thought, tool, tool_input, text
        ToolResult  フィールド: result
        AgentFinish フィールド: return_values, log
        """
        output_type = type(agent_output).__name__
        entry: dict = {"output_type": output_type}

        # ---- 戦略1: Pydantic v2 model_dump() ----
        if hasattr(agent_output, "model_dump"):
            try:
                dumped = agent_output.model_dump()
                for k, v in dumped.items():
                    if not k.startswith("_"):
                        entry[k] = _safe_val(v)
            except Exception:
                pass

        # ---- 戦略2: dict(obj) — Pydantic v1 ----
        if len(entry) <= 1:
            try:
                for k, v in dict(agent_output).items():
                    if not k.startswith("_"):
                        entry[k] = _safe_val(v)
            except Exception:
                pass

        # ---- 戦略3: vars(obj) ----
        if len(entry) <= 1:
            try:
                for k, v in vars(agent_output).items():
                    if not k.startswith("_"):
                        entry[k] = _safe_val(v)
            except Exception:
                pass

        # ---- 戦略4: 個別属性補完（戦略1〜3で取れなかったフィールドのみ追加）----
        # CrewAI 1.x で確認されている属性名リスト
        _known_attrs = (
            "thought", "tool", "tool_input", "text",   # AgentAction
            "result",                                    # ToolResult
            "log", "return_values",                     # AgentFinish (LangChain 互換)
            "content", "additional_kwargs",             # BaseMessage 系
        )
        for attr in _known_attrs:
            if attr not in entry and hasattr(agent_output, attr):
                try:
                    entry[attr] = _safe_val(getattr(agent_output, attr))
                except Exception:
                    pass

        # ---- フォールバック: 何も取れなければ str() 全体を raw に格納 ----
        if len(entry) <= 1:
            entry["raw"] = str(agent_output)

        # ---- output フィールドはオブジェクトのreprが入ることが多く冗長なので削除 ----
        # 必要な情報は上記フィールドで個別に取得済み
        entry.pop("output", None)

        return entry

    def step_callback(agent_output) -> None:
        """各 Agent の 1ステップ（ToolCall・思考・最終回答）を完全記録する。"""
        try:
            idx = _state["task_idx"]
            agent_label = _agent_labels[idx] if idx < len(_agent_labels) else f"Agent{idx + 1}"
            entry: dict = {
                "event": "step",
                "agent_num": idx + 1,
                "agent_label": agent_label,
            }
            entry.update(_extract_step_details(agent_output))
            _write(entry)
            tool_info = entry.get("tool") or entry.get("output_type", "")
            logger.debug(f"[STEP] {agent_label} type={entry['output_type']} tool={tool_info}")
        except Exception as e:
            logger.debug(f"[STEP] ログ記録失敗（分析継続）: {e}")

    def task_callback(task_output) -> None:
        """各 Task 完了時に完全出力を記録し、agent カウンターを進める。"""
        try:
            idx = _state["task_idx"]
            agent_label = _agent_labels[idx] if idx < len(_agent_labels) else f"Agent{idx + 1}"

            # TaskOutput の主要属性: description, raw, exported_output, summary, agent, name
            agent_role = ""
            if hasattr(task_output, "agent"):
                agent_role = str(getattr(task_output.agent, "role", task_output.agent))

            raw_output = getattr(task_output, "raw", str(task_output))
            entry = {
                "event": "task_done",
                "agent_num": idx + 1,
                "agent_label": agent_label,
                "agent_role": agent_role,
                "task_name": getattr(task_output, "name", ""),
                "description": getattr(task_output, "description", ""),
                "raw_output": raw_output,
                "summary": getattr(task_output, "summary", ""),
            }
            _write(entry)
            logger.info(f"[TASK DONE] {agent_label} summary={entry['summary'][:120]}")

            # デバッグモード: 各エージェント出力をリアルタイムでSlackに送信
            from src.config import DEBUG_MODE
            from src.slack.sender import send_debug_task_output
            if DEBUG_MODE and slack_client and slack_channel and slack_thread_ts:
                send_debug_task_output(
                    slack_client,
                    slack_channel,
                    slack_thread_ts,
                    agent_label,
                    raw_output,
                )

            # 次のタスク（次の Agent）へカウンターを進める
            _state["task_idx"] += 1
        except Exception as e:
            logger.debug(f"[TASK DONE] ログ記録失敗（分析継続）: {e}")

    return step_callback, task_callback


def _check_crewai_auth() -> None:
    """
    CrewAI Enterprise tracing の認証トークンを事前確認する。

    トークンが期限切れ・未取得の場合、Enterprise Batches はサイレントに
    ephemeral（非認証）モードで動作し、ダッシュボードが
    "Unknown Crew / 0 events / Running のまま" になる。

    本関数はそれを事前に検出してログ警告を出す。
    分析自体は認証状態に関わらず継続する。
    """
    # Tracing が有効になっているかチェック
    if os.environ.get("CREWAI_TRACING_ENABLED", "false").lower() != "true":
        logger.warning(
            "⚠️ CREWAI_TRACING_ENABLED が ON になっていません。"
            " Enterprise Traces が無効のまま実行される可能性があります。"
        )

    try:
        from crewai.cli.authentication.token import get_auth_token, AuthError  # type: ignore
        token = get_auth_token()
        if token:
            logger.info("CrewAI 認証トークン: 有効（Enterprise Batches に正常記録されます）")
        else:
            logger.warning(
                "⚠️ CrewAI 認証トークンが無効または期限切れです。"
                " Enterprise Batches が ephemeral モードで実行され"
                " 'Unknown Crew / 0 events / Running のまま' になります。"
                " `conda activate autoanalyzer && crewai login` を実行してトークンを更新してください。"
            )
    except Exception as e:
        logger.warning(
            f"CrewAI 認証状態を確認できませんでした ({e})。"
            " `crewai login` を実行してください。"
        )


def run_analysis(
    ticker: str,
    slack_client=None,
    slack_channel: str = "",
    slack_thread_ts: str = "",
) -> str:
    """
    証券番号を受け取り、9 Agentが協調して企業価値分析レポートを生成して返す。

    Args:
        ticker: 4桁の証券番号（例: "7203"）
        slack_client: デバッグモード時に中間出力を送信するSlack WebClient（省略可）
        slack_channel: 送信先チャンネルID（省略可）
        slack_thread_ts: 送信先スレッドのts（省略可）

    Returns:
        Markdown形式の企業価値分析レポート文字列
    """
    # Enterprise トレーシングを確実に有効化（ThreadPoolExecutor 子スレッド用の再セット）
    os.environ["CREWAI_TRACING_ENABLED"] = "true"

    # CrewAI Enterprise 認証状態を事前確認（トークン期限切れ警告）
    _check_crewai_auth()

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
    task2 = create_task2(ticker, task1)          # 対象企業ディープリサーチ (Gemini, context=task1)
    task3 = create_task3(ticker)                             # 競合情報収集 (Perplexity Sonar)
    task3a = create_task3a(ticker, task3)                    # 競合定量データ収集 (DeepSeek + StockScraperTool, context=task3)
    task3b = create_task3b(ticker, task3, task3a)            # 競合統合レポート作成 (DeepSeek, context=[task3, task3a])
    task4 = create_task4(ticker)
    task5 = create_task5(ticker, edinet_code)
    task6 = create_task6(ticker, task1)
    task7 = create_task7(ticker, task1, task2, task3, task3a, task3b, task4, task5, task6)
    task8 = create_task8(ticker, task7, task3b)
    task9 = create_task9(ticker, task7, task8, task3b)

    # Step 4: Crew構築・実行
    # Task1〜Task6を順次実行し、
    # Agent7が context=[task1..task6] で全結果を集約して最終レポートを生成する。
    # Agent6は企業のセクターを起点に業界・地政学ニュースを同心円状に収集する。
    # Agent8はAgent7のレポートに対して批判的・反論的な視点からチャレンジする。
    # Agent9は両レポートを第三者として精査し、最終投資判断を下す。
    log_dir = f"data/{ticker}"
    os.makedirs(log_dir, exist_ok=True)
    log_file_path = f"{log_dir}/crew_execution.log"
    event_log_path = f"{log_dir}/crew_events.jsonl"

    crew_name = f"AutoAnalyzer_{ticker}"

    # ローカルイベントログ（JSONL）にAgent識別・全フィールド完全出力で記録する。
    all_tasks = [task1, task2, task3, task3a, task3b, task4, task5, task6, task7, task8, task9]
    step_cb, task_cb = _make_event_logger(
        event_log_path, crew_name, all_tasks,
        slack_client=slack_client,
        slack_channel=slack_channel,
        slack_thread_ts=slack_thread_ts,
    )

    # 実行開始イベントを記録
    with open(event_log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({
            "event": "crew_start",
            "crew": crew_name,
            "ticker": ticker,
            "ts": datetime.datetime.now().isoformat(),
        }, ensure_ascii=False) + "\n")

    crew = Crew(
        name=crew_name,  # Enterprise ダッシュボードでの識別に使用
        agents=[
            task1.agent,
            task2.agent,
            task3.agent,
            task3a.agent,
            task3b.agent,
            task4.agent,
            task5.agent,
            task6.agent,
            task7.agent,
            task8.agent,
            task9.agent,
        ],
        tasks=[task1, task2, task3, task3a, task3b, task4, task5, task6, task7, task8, task9],
        process=Process.sequential,  # task6 が context で 1〜5 を参照するため sequential
        verbose=True,
        output_log_file=log_file_path, #debugの一時的なコメントアウト
        step_callback=step_cb,
        task_callback=task_cb,
        # Enterprise Batches/Traces で Completed に更新されるために必要。
        # 事前に `crewai login` の実行と CREWAI_TRACING_ENABLED=true の設定が必要。
        tracing=True,
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

    # Step 5: レポート文字列を取得（Agent6本文 + Agent7反論 + Agent8最終判断を結合）
    main_report = task7.output.raw if (task7.output and hasattr(task7.output, "raw")) else ""
    critic_section = task8.output.raw if (task8.output and hasattr(task8.output, "raw")) else ""
    final_judgment = task9.output.raw if (task9.output and hasattr(task9.output, "raw")) else ""

    sections = [s for s in [main_report, critic_section, final_judgment] if s]
    if sections:
        report_text = "\n\n---\n\n".join(s.rstrip() for s in sections)
    elif hasattr(result, "raw"):
        report_text = result.raw
    else:
        report_text = str(result)

    # ヘッダーを付与
    report_text = add_report_header(report_text, ticker)
    logger.info(f"=== AutoAnalyzer 分析完了: {ticker} ===")
    return report_text
