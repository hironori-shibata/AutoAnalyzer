"""
Task5: 株価・需給リサーチタスク
Agent5 (株価・需給リサーチャー) が担当する。
信用倍率の解釈に注意（高い＝良いではない）。
"""
from crewai import Task
from src.agents.agent5_stock import create_agent5


def create_task5(ticker: str, edinet_code: str) -> Task:
    agent = create_agent5()
    return Task(
        description=(
            f"証券番号 {ticker} について以下の需給データを収集・分析してください:\n\n"
            "1. 株探（source='kabutan_stock'）から現在株価・出来高・PER・PBR・配当利回りを取得\n"
            "2. 株探信用残（source='kabutan_margin'）から信用倍率の週次推移（直近13週）を取得\n"
            "3. 空売り.net（source='karauri'）から空売り比率・残高の日次推移（直近1ヶ月）を取得\n"
            "4. 株予報pro（source='kabuyoho'）から業績予想・テクニカル情報を取得\n"
            f"5. IR Bank（https://irbank.net/{edinet_code}）からPER・PBR・株価履歴を取得\n\n"
            "【重要な解釈ルール】\n"
            "・信用倍率が高いほどポジティブという解釈は誤り（信用買い残 ÷ 信用売り残）\n"
            "・信用倍率 > 10: 買い残過多 → 将来の返済売りリスク大（ネガティブ）\n"
            "・信用倍率の【低下】（例: 15倍 → 10倍）: 買い残の整理が進んでおり需給は【改善】と解釈すること\n"
            "・信用倍率の【上昇】: 買い残が積み上がっており需給は【悪化】と解釈すること\n"
            "・空売り比率 > 50%: 機関の売り圧力が強い\n"
            "・「水準」だけでなく「変化の方向性」を重視すること\n\n"
            "時系列データはTrendAnalysisToolで計算すること。LLMで計算しないこと。"
        ),
        expected_output=(
            "【緩和条件】情報が完全に揃わなくても構いません。取得できない場合は「該当データなし」と記載して次に進み、情報の深追いや無限ループを避けてください。\n"
            "需給状況の分析レポート（Markdown形式）。\n"
            "信用倍率・空売り比率の時系列テーブル、需給総合評価（買い圧 vs 売り圧）、"
            "現在の株価指標（PER・PBR・配当利回り）を含むこと。"
        ),
        agent=agent,
    )
