# Agent4: 業績リサーチャー 設計書

## 役割

IR Bankから複数年（5〜10年分）の業績データを取得し、  
**単一時点の数値ではなく時系列のトレンド変化**を重視して分析する。

---

## 入力

| 項目 | 説明 |
|---|---|
| `ticker` | 4桁の証券番号 |
| `edinet_code` | EdinetCode |

---

## 出力

以下の時系列データ・分析を含むMarkdownテキスト:

- 売上高の推移（5〜10年）
- 営業利益・純利益の推移
- EPS・ROE・ROAの推移
- 自己資本比率の推移
- キャッシュフロー（営業CF・投資CF・財務CF）の推移: 過去5〜10年の【確定通期実績】のみを抽出し、FCF（営業CF + 投資CF）の時系列リストを作成すること
- 配当金・配当性向の推移
- 各指標のトレンド評価（改善傾向/悪化傾向/横ばい）
- 特異な変動があった年のピックアップと推定原因

---

## 取得するデータリソース

| データ | URL | 取得方法 |
|---|---|---|
| 会社業績（複数年） | `irbank.net/{edinet_code}/results` | Jina Reader / BeautifulSoup |

> **注意**: 最新期のデータはAgent3（決算短信）から取得するため、Agent4はそれ以前の年度を補完する役割。  
> 両者のデータを統合する際は重複に注意すること。

---

## 使用するTool

| Tool名 | 説明 |
|---|---|
| `fetch_with_jina(url)` | IR BankのResultsページ取得 |
| `IRBankScraperTool` | 表データをパースしてdict/DataFrameに変換 |
| `TrendAnalysisTool` | Python Toolによるトレンド計算 |

---

## Python Tool: `TrendAnalysisTool`

LLMに数値の変化率・CAGR・トレンド方向を計算させてはならない。

```python
def analyze_trend(values: list[float], years: list[int]) -> dict:
    """
    時系列データのトレンドをPythonで計算する。
    LLMに計算させない。
    """
    import numpy as np

    if len(values) < 2:
        return {"error": "データが不足しています"}

    # CAGR計算
    n = len(values) - 1
    cagr = (values[-1] / values[0]) ** (1 / n) - 1 if values[0] != 0 else None

    # 線形トレンドの傾き（正:改善, 負:悪化）
    x = np.arange(len(values))
    slope = float(np.polyfit(x, values, 1)[0])

    # 直近3年変化率
    recent_change = (values[-1] / values[-4] - 1) if len(values) >= 4 else None

    return {
        "latest_value": values[-1],
        "oldest_value": values[0],
        "cagr": round(cagr, 4) if cagr is not None else None,
        "slope_direction": "改善" if slope > 0 else "悪化" if slope < 0 else "横ばい",
        "recent_3yr_change": round(recent_change, 4) if recent_change else None,
        "values": values,
        "years": years,
    }
```

---

## 分析の重点ポイント

Agent4のLLMは以下の観点でトレンドを評価すること:

1. **売上成長の持続性**: 増収が続いているか、一時的か
2. **利益率の方向性**: 利益率が拡大・縮小しているか
3. **ROE・ROAの変化**: 資本効率が改善しているか
4. **CF構造の健全性**: 営業CFがプラス安定か、投資CFとのバランス
5. **財務健全性**: 自己資本比率の変化
6. **配当方針**: 増配傾向か、減配歴があるか

---

## CrewAI Agent定義

```python
# src/agents/agent4_performance.py
from crewai import Agent
from src.tools.irbank_scraper import IRBankScraperTool
from src.tools.financial_calc import TrendAnalysisTool

agent4 = Agent(
    role="業績トレンドリサーチャー",
    goal=(
        "複数年にわたる業績データを収集し、時系列トレンドを分析すること。"
        "単一時点の数値ではなく、変化の方向性と持続性を重視すること。"
        "数値計算はPython Toolに委ねること。"
    ),
    backstory=(
        "あなたは長期投資家の視点から企業の業績推移を分析する専門家です。"
        "5〜10年の時系列データから企業の実力と成長軌道を読み解きます。"
    ),
    tools=[IRBankScraperTool(), TrendAnalysisTool()],
    llm=llm,
    verbose=True,
    max_iter=10,
)
```

---

## CrewAI Task定義

```python
task4 = Task(
    description=(
        "EdinetCode {edinet_code} の企業について、"
        "irbank.net/{edinet_code}/results から複数年（5〜10年）の業績データを取得し、"
        "以下の時系列トレンドを分析してください:\n"
        "- 売上高・営業利益・純利益の推移\n"
        "- EPS・ROE・ROAの推移\n"
        "- 自己資本比率・キャッシュフローの推移\n"
        "- 配当の推移\n\n"
        "各指標はPython Toolで計算させること（LLMで計算しない）。\n"
        "単一の数値ではなく、変化の方向性と持続性を重視すること。"
    ),
    expected_output=(
        "時系列データを含む業績分析レポート（Markdown形式）。"
        "各指標の推移テーブルとトレンド評価コメントを含むこと。"
    ),
    agent=agent4,
)
```

---

## 注意事項

- 最新決算期のデータはAgent3から取得するため、重複しないよう整合すること
- LLMによるCAGR・変化率の計算は禁止。必ず`TrendAnalysisTool`を使うこと
- 単位の統一（百万円表記 etc.）をスクレイピング時に確認すること
