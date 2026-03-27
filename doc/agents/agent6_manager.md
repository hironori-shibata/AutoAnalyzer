# Agent6: 統括マネージャー 設計書

## 役割

Agent1〜5の出力をすべて `context` で集約し、企業価値算定（DCF法・マルチプル法）を行い、  
最終的な企業価値分析レポートを生成する。  
計算はすべてPython Toolに委ねる。

---

## 入力

| 項目 | 説明 |
|---|---|
| Agent1の出力 | 有報定性情報（リスク・事業内容等） |
| Agent2の出力 | 競合・業界構造分析（PER・EV/EBITDA含む） |
| Agent3の出力 | 最新決算財務指標・セグメント業績・配当情報 |
| Agent4の出力 | 複数年業績トレンド・配当推移 |
| Agent5の出力 | 株価・需給情報 |
| `ticker` | 4桁の証券番号 |
| MarkdownReadTool | 欠落データのフォールバック読み込み |

> **廃止:** LlamaIndexによるRAGクエリはLlamaIndex廃止に伴い削除済み。
> 代わりに `MarkdownReadTool` で生データを直接読み込む。

---

## 出力

最終的な企業価値分析レポート（Markdown形式）:

```markdown
# 企業価値分析レポート: {企業名} ({証券番号})
生成日時: YYYY-MM-DD HH:MM

## 1. 企業概要・事業内容
## 2. 業界構造・競争環境分析
## 3. 最新決算財務指標（セグメント業績と配当方針）
## 4. 複数年業績推移（配当・配当性向のトレンドを含む）
## 5. 株価・需給状況
## 6. 企業価値算定
   ### 6-1. DCF法による企業価値
   ### 6-2. マルチプル法（同業種比較）
   ### 6-3. 総合評価・現在株価との乖離
## 7. リスク・課題
| リスク項目 | 影響度 | 根拠・分析 |
|---|---|---|
| {リスク名} | **{大/中/小}** | {影響度判定の根拠} |
## 8. 投資判断サマリー
```

---

## 企業価値算定: DCF法

### 使用するPython Tool: `DCFValuationTool`

```python
# 入力パラメータ例
dcf_input = {
    # Agent3・Agent4から取得（すべて「円単位」に換算してから渡す）
    "free_cash_flows": [3_000_000_000_000, 3_500_000_000_000],  # 過去FCF
    "revenue_cagr": 0.05,         # 売上CAGR（Agent4 TrendAnalysisToolの結果）
    "operating_margin": 0.08,     # 営業利益率（Agent3から）
    "shares_outstanding": 13_033_236_606,  # 発行済株式数
    "net_debt": 34_208_773_000_000,        # 純有利子負債（円単位）

    # WACC計算パラメータ
    "risk_free_rate": 0.015,       # 無リスク利子率（日本10年国債利回り）
    "equity_risk_premium": 0.06,
    "beta": 1.1,                  # デフォルト ※企業固有ベータは取得困難
    "debt_cost": 0.01,
    # ↓ 重要: 自己資本比率から動的に算出する
    "debt_ratio": 0.62,           # = 1 - 自己資本比率(0.38) をAgent6が計算してから渡す

    # 継続価値パラメータ
    "terminal_growth_rate": 0.007, # 永久成長率 0.7%（日本の低成長環境を考慮）
    "projection_years": 5,
}
```

### DCF計算フロー

```
1. WACCの計算
   Re = Rf + β × ERP （CAPM）
   WACC = E/(D+E) × Re + D/(D+E) × Rd × (1 - T)

2. 将来FCFの予測（直近FCFをベースに revenue_cagr で成長）

3. FCFの現在価値計算
   PV = Σ FCFt / (1 + WACC)^t  (t=1〜5)

4. 継続価値（Terminal Value）の計算
   TV = FCF_n × (1 + g) / (WACC - g)  ※ g=0.7%

5. 事業価値 = PV(FCF) + PV(TV)

6. 株式価値 = 事業価値 - 純有利子負債

7. 理論株価 = 株式価値 / 発行済株式数
```

### 単位の自動補正

入力が「百万円単位」の場合（`EV < 株数×10` の判定）、内部で自動的に100万倍補正する。  
補正した場合は出力の `note` フィールドに記録される。

---

## 企業価値算定: マルチプル法

### 使用するPython Tool: `MultiplesValuationTool`

```python
multiples_input = {
    "target_eps": 233.0,                   # Agent3から（1株あたり・円単位）
    "target_ebitda": 5_600_000_000_000,    # 円単位に換算（任意）
    "target_net_debt": 34_208_773_000_000, # 円単位に換算（任意）

    # Agent2が取得した競合他社データ
    "peer_pers":       [12.0, 14.0, 10.0],
    "peer_ev_ebitdas": [6.0, 7.0, 8.0],   # 任意（データがある場合のみ）

    "shares_outstanding": 13_033_236_606,
}
```

---

## CrewAI Agent定義（実装済み）

```python
# src/agents/agent6_manager.py
from crewai import Agent
from src.config import get_llm
from src.tools.valuation_calc import DCFValuationTool, MultiplesValuationTool
from src.tools.file_reader import MarkdownReadTool

def create_agent6() -> Agent:
    return Agent(
        role="統括マネージャー・企業価値アナリスト",
        goal=(
            "各リサーチャーAgentの情報を統合し、DCF法・マルチプル法で企業価値を算定し、"
            "現在株価との乖離から投資判断サマリーを提供すること。"
            "すべての数値計算はPython Toolで行うこと。LLM自身は計算しない。"
        ),
        backstory=(...),
        tools=[DCFValuationTool(), MultiplesValuationTool(), MarkdownReadTool()],
        llm=get_llm(),
        verbose=True,
        max_iter=35,
    )
```

> **LLM選択:** Agent6では `get_llm()` (deepseek-chat V3) を使用する。
> `deepseek-reasoner` (R1) はFunction Calling（ツール呼び出し）との互換性が低いため使用しない。

---

## CrewAI Task定義

```python
# src/tasks/task6_report.py
from crewai import Task

def create_task6(ticker, task1, task2, task3, task4, task5):
    return Task(
        description=(
            "以下の各Agentの調査結果を統合し、証券番号 {ticker} の総合企業価値分析レポートを作成してください。\n"
            "...\n"
            "6. DCF法による理論株価（DCFValuationToolで計算）\n"
            "   - Agent4から: 過去5〜10年の【確定通期実績】に基づくFCFリスト、売上CAGR\n"
            "   - Agent3から: 最新の営業利益率、発行済株式数、純有利子負債、負債比率\n"
            "   - ⚠️ DCFの入力（free_cash_flows）には、Agent3による四半期からの年間化推定値ではなく、必ずAgent4が収集した『確定した複数年実績』を使用すること。\n"
            "   - ⚠️ 計算の透明性を確保するため、レポートには将来5年間の予測FCFリストをテーブル形式で明示すること。\n"
            "   - ⚠️ 継続価値（TV）が全体に占める割合を記載し、異常に高い場合（90%以上）は注意を促すこと。\n"
            "7. マルチプル法による理論株価（MultiplesValuationToolで計算）\n"
            "...\n"
            "9. 主要リスク・課題: Agent1から提供されるリスク情報（JSON形式）を読み込み、影響度（大・中・小）とその根拠を含めてテーブル形式でまとめること。\n"
        ),
        expected_output=(
            "Markdown形式の完全な企業価値分析レポート。\n"
            "「7. リスク・課題」セクションには、リスク項目、影響度、根拠・分析を含むテーブルを必ず含めること。"
        ),
        agent=create_agent6(),
        context=[task1, task2, task3, task4, task5],
    )
```

---

## 業界構造・競争優位性分析

Agent6のLLMが担当する定性分析（計算不要のため）:

- **5フォース分析**: 既存競合/新規参入/代替品/買い手/売り手の脅威
- **競争優位性の源泉**: ブランド・特許・コスト・ネットワーク効果・スイッチングコスト
- **セグメント別業績**: 主力事業と成長事業の特定（Agent3から）
- **配当・配当性向の評価**: 増配傾向か、減配歴があるか（Agent3・Agent4から）

---

## 注意事項

- DCF計算の `debt_ratio` は **Agent3の自己資本比率から `1 - equity_ratio` で算出して渡すこと**（一律 0.3 でなく企業固有値を使う）
- `terminal_growth_rate` のデフォルトは **0.01（1%）**（日本の低成長環境に合わせ2%から引き下げ済み）
- マルチプル法は、競合データが取得しやすい PER法 を主軸とする。EV/EBITDA法はデータがある場合のみ参考値として算出する。**データがない場合にLLMの判断で数値を勝手な仮定（例：10.0倍とする等）で補完することは厳禁。**
- 金融事業を多く持つ企業（トヨタ等）では EV/EBITDA 法の結果が実態と乖離する可能性がある
- 最後の「投資判断サマリー」は参考意見として提供し、最終判断はユーザーに委ねる旨を明記
- **いかなる数値計算もLLM自身で行ってはならない。必ずPython Toolに委ねること**
