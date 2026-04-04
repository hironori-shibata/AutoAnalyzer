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
            "複数年（5〜10年）の業績データを取得し、以下の時系列トレンドを分析してください:\n\n"
            "【データ取得手順】\n"
            f"まず IRBankFinancialTableTool（edinet_code='{edinet_code}'）を呼び出して、"
            "兆・億変換済みの構造化JSONを取得してください。\n"
            "このツールが返すJSONには pl（損益）・bs（貸借）・cf（CF）・dividend（配当）の4セクションがあり、"
            "すべての monetary 値は円（1円単位）、比率・マージンは % で格納されています。\n"
            "cf セクションの free_cf フィールドは IR Bank 掲載値（営業CF＋投資CF計算済み）であり、"
            "符号ミスは発生しません。investing_cf は通常マイナス値です。\n"
            "⚠️ FCFリストの抽出: cf セクションから confirmed_only=True（デフォルト）の確定通期実績行のみを使用し、"
            "各行の free_cf 値を古い順に並べたリストを作成してください。\n"
            "⚠️ FCFが None の年は除外してリストに含めないでください。\n\n"
            "⚠️ 【単位変換の厳守 – 間違えると後続エージェントのDCFが狂う】\n"
            "ツールが返す金額はすべて1円単位の生の数値です。\n"
            "テーブルを「億円」表記で作成するときは必ず 100,000,000（＝1億＝10^8）で割ること。\n"
            "  正: 243,800,000,000 ÷ 100,000,000 = 2,438 億円  ← これが正しい\n"
            "  誤: 243,800,000,000 ÷  10,000,000 = 24,380 億円 ← 10倍大きい（千万割りは誤り）\n"
            "【サニティチェック（必須）】\n"
            "出力するFCFの最大値が同年度の売上高を超えている場合、単位変換が誤っています。\n"
            "FCF ÷ 売上 = 10〜30%程度が現実的な範囲です。\n\n"
            "【取得対象データ（全社ベース）】\n"
            "- pl.revenue（売上高）の推移\n"
            "- pl.operating_profit（営業利益）・pl.net_income（純利益）の推移\n"
            "- pl.eps・pl.roe・pl.roa の推移\n"
            "- bs.equity_ratio（自己資本比率）の推移\n"
            "- cf.operating_cf・cf.investing_cf・cf.free_cf の推移\n"
            "- dividend.dividend_per_share（一株配当）・dividend.payout_ratio（配当性向）の推移\n\n"
            "【セグメント別成長率の収集】\n"
            "- IR Bank のセグメント情報ページ（例: https://irbank.net/{edinet_code}/segment）を"
            "IRBankScraperToolで取得するなどして、主要セグメント別の過去3〜5年間の売上高推移を取得すること\n"
            "- 各セグメントの売上推移をTrendAnalysisToolに渡してセグメント別CAGRを計算\n"
            "- 最新年度の各セグメント売上構成比（weight）も抽出すること\n"
            "- これらはAgent6のセグメント別加重平均CAGR計算に使用される\n"
            "- 【将来成長率の前提】各セグメントの将来成長率見通しを以下から収集すること:\n"
            f"  a) 会社側のセグメント別業績見通し・中期経営計画（増減率ガイダンス）\n"
            f"  b) IRBankScraperTool等を使って「{ticker}」のセグメント成長率・将来見通しに関する情報を収集し、業界レポートや会社ガイダンスを取得\n"
            "  c) 過去CAGRと将来見通しを対比テーブルで示し、DCFに推奨するCAGR（どちらを使うべきか）にコメントを付けること\n"
            "  d) セグメントミックス変化が営業利益率に与える影響方向（改善/悪化/横ばい）とその規模感を示すこと\n"
            "     → 例: 低利益の自動車セグメントが縮小し高利益の半導体セグメントが拡大 → 利益率改善方向\n"
            "     → これがAgent6が逆DCFのexpected_growth_rateおよびebitda_0を設定する際の根拠となる\n"
            "  ※ 将来見通しが取得できない場合は過去CAGRを使用し「過去CAGR適用」と明記すること\n\n"
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
            "トレンド評価コメントを含むこと。\n"
            "【セグメント別成長率サマリー】セクションを設け、各セグメントの売上CAGR・構成比・成長特性を記載すること。\n"
            "（Agent6がDCFにセグメント別加重平均CAGRを使用するために必要）\n"
            "【将来成長率前提テーブル】過去CAGR vs 会社ガイダンス/業界見通しの対比テーブルを記載すること。\n"
            "セグメントミックス変化による margin_drift の推定方向（プラス/マイナス/ゼロ）とその根拠も含めること。"
        ),
        agent=agent,
    )
