"""
Task4: 業績トレンドリサーチタスク
Agent4 (業績トレンドリサーチャー) が担当する。
複数年の業績データを収集し、TrendAnalysisToolで計算する。
"""
from crewai import Task
from src.agents.agent4_performance import create_agent4


def create_task4(ticker: str, edinet_code: str) -> Task:
    agent = create_agent4()
    return Task(
        description=(
            f"EdinetCode {edinet_code}（証券番号: {ticker}）の企業について、\n"
            f"https://irbank.net/{edinet_code}/results から複数年（5〜10年）の業績データを取得し、"
            "以下の時系列トレンドを分析してください:\n\n"
            "【取得対象データ】\n"
            "- 売上高の推移\n"
            "- 営業利益・純利益の推移\n"
            "- EPS・ROE・ROAの推移\n"
            "- 自己資本比率の推移\n"
            "- キャッシュフロー（営業CF・投資CF・財務CF）の推移: 過去5〜10年の【確定通期実績】のみを抽出し、FCF（営業CF + 投資CF）の時系列リストを作成すること\n"
            "- 配当金・配当性向の推移\n"
            "⚠️ FCFの算出には、四半期累計ではなく、必ず『確定した年度ごとの数値』を使用してください。\n\n"
            "【分析方法】\n"
            "各指標の時系列リストをTrendAnalysisToolに渡してCAGR・トレンド方向・直近変化率を計算すること。\n"
            "LLMでCAGRや変化率を計算しないこと。\n\n"
            "【評価観点】\n"
            "- 売上成長の持続性（増収が続いているか、一時的か）\n"
            "- 利益率の方向性（拡大・縮小）\n"
            "- ROE・ROAの変化（資本効率の改善・悪化）\n"
            "- CF構造の健全性（営業CFがプラス安定か）\n"
            "- 財務健全性（自己資本比率の変化）\n"
            "- 配当方針（増配傾向か、減配歴があるか）"
        ),
        expected_output=(
            "【緩和条件】情報が完全に揃わなくても構いません。取得できない場合は「該当データなし」と記載して次に進み、情報の深追いや無限ループを避けてください。\n"
            "時系列データを含む業績分析レポート（Markdown形式）。\n"
            "各指標の推移テーブルとTrendAnalysisToolの計算結果（CAGR・トレンド方向）、"
            "トレンド評価コメントを含むこと。"
        ),
        agent=agent,
    )
