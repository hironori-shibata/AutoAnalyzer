"""
Task5: 業績トレンドリサーチタスク
Agent5 (業績トレンドリサーチャー) が担当する。
複数年の業績データを収集し、TrendAnalysisToolで計算する。
"""
from crewai import Task
from src.agents.agent5_performance import create_agent5


def create_task5(ticker: str, edinet_code: str) -> Task:
    agent = create_agent5()
    return Task(
        description=(
            f"EdinetCode {edinet_code}（証券番号: {ticker}）の企業について、"
            "複数年（5〜10年）の業績データを取得し、時系列トレンドを分析してください。\n\n"
            "【手順1: 財務データ取得・全指標トレンド一括計算】\n"
            f"IRBankTrendBatchTool（edinet_code='{edinet_code}'）を1回呼び出す。\n"
            "このツールはIR Bankからのデータ取得とトレンド計算を内部で一括処理する。\n"
            "レスポンスの構造:\n"
            "  raw     : 生の財務データ（pl/bs/cf/dividend）。推移テーブルの表示に使用する。\n"
            "            monetary値はすべて円（1円単位）。比率・マージンは%。\n"
            "  trends  : 売上・営業利益・純利益・EPS・ROE・ROA・営業利益率・自己資本比率・\n"
            "            営業CF・投資CF・FCF・一株配当・配当性向のCAGR・トレンド方向・直近変化率。\n"
            "⚠️ IRBankFinancialTableTool を別途呼ぶ必要はない。\n"
            "⚠️ 財務テーブル指標に対して TrendAnalysisTool を個別に呼ぶことは禁止。\n\n"
            "⚠️ 【単位変換の厳守 – 後続エージェントのDCFに影響する】\n"
            "raw の monetary値はすべて1円単位の生の数値。\n"
            "テーブルを「億円」表記で作成するときは必ず 100,000,000（10^8）で割ること。\n"
            "FCF ÷ 売上 = 10〜30%程度が現実的な範囲。これを超える場合は単位変換の誤りを疑うこと。\n\n"
            "【手順2: セグメント別成長率の一括収集】\n"
            f"IRBankScraperTool（edinet_code='{edinet_code}', section='segment'）で"
            "主要セグメント別の過去3〜5年間の売上高推移テーブルを取得すること。\n"
            "テーブルから全セグメントの数値を読み取り、SegmentTrendBatchTool を1回だけ呼び出すこと。\n"
            "引数: segment_names（セグメント名リスト）・segment_values（各セグメントの数値リスト、古い順）・years（共通年度リスト）。\n"
            "⚠️ TrendAnalysisTool をセグメントごとに個別に呼び出すことは禁止。\n"
            "SegmentTrendBatchTool の返却値に weighted_avg_cagr（加重平均CAGR）と latest_weight（構成比）が含まれる。\n"
            "（後続Agent7がDCFにセグメント別加重平均CAGRを使用するために必要）\n\n"
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
            "IRBankTrendBatchToolの計算結果（CAGR・トレンド方向）に基づく各指標の推移テーブルと"
            "トレンド評価コメントを含むこと。\n"
            "【セグメント別成長率サマリー】セクションを設け、各セグメントの売上CAGR・構成比を記載すること。\n"
            "（Agent7がDCFに使用するexpected_growth_rateの根拠となる売上CAGRを必ず明示すること）"
        ),
        agent=agent,
    )
