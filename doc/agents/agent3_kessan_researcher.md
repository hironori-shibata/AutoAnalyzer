# Agent3: 最新決算短信リサーチャー 設計書

## 役割

IR Bankから最新の決算短信PDFを取得・Markdown変換し、  
**Python Toolを使って** 各種財務指標を計算する。  
LLMには計算をさせず、すべての数値計算はPython Toolに委譲すること。  
セグメント別の業績と配当情報も抽出する。

---

## 入力

| 項目 | 説明 |
|---|---|
| `ticker` | 4桁の証券番号 |

---

## 出力

以下の財務指標を含むMarkdownテキスト（最新決算期分）:

| 指標 | 説明 |
|---|---|
| ROA | 総資産利益率 |
| ROE | 自己資本利益率 |
| EPS | 1株当たり利益 |
| 売上高営業利益率 | 営業利益 ÷ 売上高 |
| 自己資本比率 | 自己資本 ÷ 総資産 |
| 流動比率 | 流動資産 ÷ 流動負債 |
| D/Eレシオ | 有利子負債 ÷ 自己資本 |
| 総資産回転率 | 売上高 ÷ 総資産（デュポン分解の効率性指標） |
| 売上高純利益率 | 当期純利益 ÷ 売上高（デュポン分解の収益性指標） |
| 財務レバレッジ | 総資産 ÷ 自己資本（デュポン分解の安全性指標） |
| CCC | 棚卸資産回転日数 + 売上債権回転日数 − 仕入債務回転日数 |
| FCF | 営業CF - 設備投資（Python Toolで計算） |
| セグメント別業績 | 各セグメントの売上・利益・構成比 |
| 配当・配当性向 | 今期の配当実績・予想・配当性向 |
| ROEの質的分析 | デュポン分解に基づいたROE生成構造の分析 |

---

## 処理フロー

```
1. KessanFetcherTool で決算短信PDFを取得・doclingでMarkdown変換
2. data/{ticker}/kessan_tansin.md に保存
3. MarkdownReadTool で生データを直接読み込む (Agent3がツールを使って読む)
4. Markdownから財務数値を抽出（LLMが担当）
   - 単位（百万円・千円等）を確認し、円に統一してからToolに渡す
5. 抽出した数値をFinancialCalcTool に渡して指標計算
6. セグメント別の業績情報（売上・利益・構成比）を抽出
7. 配当・配当性向に関する記述を抽出
8. 計算結果と定性情報をまとめてレポート出力
```

> **変更:** LlamaIndex (RAG) によるインデックス化・クエリは廃止。
> `MarkdownReadTool` でMDファイルを直接読み込む方式に変更済み。

---

## 使用するTool

| Tool名 | 説明 |
|---|---|
| `KessanFetcherTool` | 決算短信PDFを取得しMarkdownに変換・保存する |
| `FinancialCalcTool` | 財務指標を一括計算する（`FinancialCalcTool`） |
| `MarkdownReadTool` | 保存済みのMarkdownファイルを直接読み込む |

---

## CrewAI Agent定義（実装済み）

```python
# src/agents/agent3_kessan.py
from crewai import Agent
from src.config import get_llm
from src.tools.kessan_fetcher import KessanFetcherTool
from src.tools.financial_calc import FinancialCalcTool
from src.tools.file_reader import MarkdownReadTool

def create_agent3() -> Agent:
    return Agent(
        role="最新決算短信リサーチャー",
        goal=(
            "最新の決算短信PDFを取得・解析し、"
            "財務指標をPython Toolで正確に計算すること。"
        ),
        backstory=(...),
        tools=[KessanFetcherTool(), FinancialCalcTool(), MarkdownReadTool()],
        llm=get_llm(),
        verbose=True,
        max_iter=10,
    )
```

---

## CrewAI Task定義（実装済み）

```python
task3 = Task(
    description=(
        "証券番号 {ticker} の最新決算短信について以下を実施:\n"
        "1. KessanFetcherTool で最新決算短信Markdownを取得\n"
        "2. 財務数値（純利益・総資産・自己資本・株式数・売上高・営業利益・営業CF・設備投資等）を抽出\n"
        "   ⚠️ FCFの年間化推定（Q3を4/3倍するなど）は厳禁。最新四半期の累計実績のみを抽出すること。\n"
        "3. FinancialCalcTool で ROA/ROE/EPS/営業利益率/自己資本比率/流動比率/DE比率/CCC/デュポン分解要素/FCF を計算\n"
        "4. デュポン分解（利益率×回転率×レバレッジ）を用いてROEの「質」を分析\n"
        "5. セグメント別の業績（売上構成や利益率）を抽出し、主力事業と成長事業を特定\n"
        "7. 今期の配当（実績・予想）および配当性向に関する記述を抽出\n"
        "⚠️ 数値計算は必ずFinancialCalcToolで行うこと。\n"
        "⚠️ 単位（百万円・千円等）を確認し、すべて円に統一してからToolに渡す。"
    ),
    expected_output=(
        "最新決算期の財務指標一覧のMarkdownレポート。\n"
        "デュポン分解（ROEの質的分析）セクションを必ず含めること。\n"
        "FCF（営業CF - 設備投資、Toolで計算）・セグメント別業績のサマリー・配当および配当性向のサマリーも含めること。"
    ),
    agent=agent3,
)
```

---

## 注意事項

- **数値計算は必ずPython Toolで行う。LLMに計算させない**
- PDFが取得できない場合はエラーをAgent6に通知し、処理をスキップ
- doclingの変換に時間がかかるため、LLMタイムアウトは400秒を設定
- 財務数値の単位（百万円・千円等）をMarkdownから正確に読み取り、円に統一してからToolに渡す
- **LlamaIndex (RAG) は廃止済み**。生データをMarkdownReadToolで直接読む
