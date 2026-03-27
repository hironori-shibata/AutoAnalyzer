# Python計算ツール仕様書

## 基本方針

- **すべての数値計算はPython Toolで行う。LLMに計算させない。**
- ToolはCrewAIの `BaseTool` を継承して実装する
- 入力バリデーションには `pydantic` の `BaseModel` を使用する
- ゼロ除算・None値・負数を安全に処理すること

---

## `FinancialCalcTool`

**ファイル**: `src/tools/financial_calc.py`  
**使用Agent**: Agent3  
**Tool name属性**: `"FinancialCalcTool"`

### インターフェース

```python
class FinancialCalcInput(BaseModel):
    net_income: float           # 当期純利益
    total_assets: float         # 総資産
    equity: float               # 自己資本（純資産）
    shares_outstanding: float   # 発行済株式数
    revenue: float              # 売上高
    operating_income: float     # 営業利益
    current_assets: float       # 流動資産
    current_liabilities: float  # 流動負債
    interest_bearing_debt: float # 有利子負債
    inventory: float            # 棚卸資産
    receivables: float          # 売上債権
    payables: float             # 仕入債務
    cogs: float                 # 売上原価

class FinancialCalcTool(BaseTool):
    name: str = "FinancialCalcTool"  # 英語名に統一（ハルシネーション防止）
```

### 出力

| キー | 説明 |
|---|---|
| `ROA` | 純利益 / 総資産 |
| `ROE` | 純利益 / 自己資本 |
| `EPS` | 純利益 / 発行済株式数 |
| `operating_margin` | 営業利益 / 売上高 |
| `equity_ratio` | 自己資本 / 総資産 |
| `current_ratio` | 流動資産 / 流動負債 |
| `de_ratio` | 有利子負債 / 自己資本 |
| `asset_turnover` | 売上高 / 総資産 |
| `ccc_days` | 棚卸資産回転日数 + 売上債権回転日数 - 仕入債務回転日数 |

---

## `TrendAnalysisTool`

**ファイル**: `src/tools/financial_calc.py`（同ファイルに定義）  
**使用Agent**: Agent4, Agent5  
**Tool name属性**: `"TrendAnalysisTool"`

### インターフェース

```python
class TrendAnalysisInput(BaseModel):
    values: list[float]   # 時系列データ（古い順）
    years: list[int]      # 対応する年度リスト

class TrendAnalysisTool(BaseTool):
    name: str = "TrendAnalysisTool"
```

### CAGR計算の注意点（バグ修正済み）

> **修正済み:** 時系列データに「赤字（負の数値）」や「ゼロ」が含まれる場合、
> 数学的にCAGRが定義できない（複素数・ゼロ割になる）ため、
> 以下のガードを実装済み。

```python
# 修正後の安全なCAGR計算
if values[0] <= 0 or values[-1] <= 0:
    cagr = None  # 計算不能とする (クラッシュさせない)
else:
    cagr = (values[-1] / values[0]) ** (1 / n) - 1
```

### 出力

| キー | 説明 |
|---|---|
| `cagr` | 年平均成長率（負数含む場合は None） |
| `trend` | `"改善"` / `"悪化"` / `"横ばい"` |
| `recent_3yr_change_rate` | 直近3年の変化率 |
| `latest_value` | 最新値 |
| `data_points` | データ点数 |

---

## `DCFValuationTool` （旧 `ValuationCalcTool` から分割）

**ファイル**: `src/tools/valuation_calc.py`  
**使用Agent**: Agent6  
**Tool name属性**: `"DCFValuationTool"`

> **変更履歴:** 旧 `ValuationCalcTool` は1ツールにDCF法・マルチプル法を混在させており、
> LLMが引数を正しく渡せないことが多かったため、2つのToolに分割した。

### インターフェース（入力）

```python
class DCFInput(BaseModel):
    free_cash_flows: list[float]       # 過去のFCF（直近3〜5年・古い順）
    revenue_cagr: float                # 売上CAGR（Agent4から）
    operating_margin: float            # 営業利益率（Agent3から）
    shares_outstanding: float          # 発行済株式数
    net_debt: float                    # 純有利子負債（負なら純現金）
    tax_rate: float = 0.30
    capex_ratio: float = 0.05
    risk_free_rate: float = 0.01
    equity_risk_premium: float = 0.055
    beta: float = 1.0
    debt_cost: float = 0.02
    debt_ratio: float = 0.3            # 負債比率: Agent3の自己資本比率から 1-equity_ratio で算出して渡すこと
    terminal_growth_rate: float = 0.01 # 永久成長率 (1%、2026年修正)
    projection_years: int = 5
```

### 単位の自動補正ロジック（実装済み）

LLMが「百万円単位」の数値をそのまま渡してしまう問題に対処するため、  
**企業価値(EV)のスケールが 発行済株式数×10 を下回る場合** に、100万倍補正を自動実行する。

```python
# 単位不整合（百万円単位入力）の自動補正
if p.shares_outstanding > 1_000_000:
    if enterprise_value < p.shares_outstanding * 10:
        # 入力が百万円単位と判定 → 全額を1,000,000倍に補正
        intrinsic_price *= 1_000_000
        enterprise_value *= 1_000_000
        ...
```

### WACC計算

```
Re = Rf + β × ERP  （CAPM）
WACC = (1 - debt_ratio) × Re + debt_ratio × Rd × (1 - T)
```

> **推奨:** `debt_ratio` には `1 - 自己資本比率` を渡すこと。
> デフォルト 0.3 (30%) は異なる企業でも同一WACCになるため使用しない。

---

## `MultiplesValuationTool` （旧 `ValuationCalcTool` から分割）

**ファイル**: `src/tools/valuation_calc.py`  
**使用Agent**: Agent6  
**Tool name属性**: `"MultiplesValuationTool"`

### インターフェース（入力）

```python
class MultiplesInput(BaseModel):
    target_eps: float              # 対象企業EPS（Agent3から・1株あたり）
    target_ebitda: float           # 対象企業EBITDA（円単位）
    target_net_debt: float         # 純有利子負債（円単位）
    peer_pers: list[float]         # 同業他社のPER一覧（Agent2から）
    peer_ev_ebitdas: list[float]   # 同業他社のEV/EBITDA一覧（Agent2から）
    shares_outstanding: float      # 発行済株式数
```

### 計算方法

```
PER法:
  median_per = median(peer_pers)
  per_price  = target_eps × median_per

EV/EBITDA法:
  median_ev_ebitda = median(peer_ev_ebitdas)
  EV = target_ebitda × median_ev_ebitda
  ev_ebitda_price = (EV - target_net_debt) / shares_outstanding

平均理論株価:
  average_price = (per_price + ev_ebitda_price) / 2
```

### 注意事項

> **金融業を多く抱える企業（例: トヨタ自動車）は、**
> EV/EBITDA法で純有利子負債（約34兆円）を差し引くと、
> 理論株価が現実の株価（3000円台）より極端に低くなる（数百円）。
> これはバグではなく「EV/EBITDA法が金融事業を抱える企業に不向き」な仕様上の限界。
> Agent6はこの旨を考察として記載することが望ましい。

---

## テスト方針

各Toolに対して以下のテストを `tests/test_tools.py` に実装すること:

- 正常系: 標準的な入力で期待通りの結果が出るか
- 境界値: ゼロ除算が発生しないか（分母が0のケース）
- 異常系: 必須フィールド欠損時にバリデーションエラーが出るか
- 負数CAGR: TrendAnalysisToolに負の数値を含むリストを渡してもクラッシュしないか
- 単位補正: DCF/MultiplesToolに「百万円単位」の数値を渡して自動補正されるか
