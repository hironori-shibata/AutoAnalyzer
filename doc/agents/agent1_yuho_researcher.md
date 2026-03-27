# Agent1: 有報リサーチャー 設計書

## 役割

有価証券報告書（有報）から企業の定性情報・事業内容・リスク・大株主構造などを収集し、  
企業の「顔」となる基礎情報をまとめる。

---

## 入力

| 項目 | 説明 |
|---|---|
| `ticker` | 4桁の証券番号 |
| `edinet_code` | EdinetCode（`code_converter.py`で変換済み） |
| `document_code` | Edinet APIから取得したdocumentcode |

---

## 出力

以下の項目を含むMarkdownテキスト:

- 事業内容サマリー
- 主要セグメントと売上構成
- リスク情報（上位5件）
- 経営課題
- 研究開発の状況
- 大株主構成（上位10位）
- 親会社・連結会社の関係
- 従業員状況（人数・平均年齢・平均年収）
- 会社の沿革ハイライト
- 設備状況の概要

---

## 取得するデータリソース

| セクション | URL | 取得方法 |
|---|---|---|
| 事業内容 | `irbank.net/{edinet_code}/business?f={document_code}` | Jina Reader |
| リスク | `irbank.net/{edinet_code}/risk?f={document_code}` | Jina Reader |
| 課題 | `irbank.net/{edinet_code}/task?f={document_code}` | Jina Reader |
| 研究開発 | `irbank.net/{edinet_code}/rd?f={document_code}` | Jina Reader |
| 大株主 | `irbank.net/{edinet_code}/notes/MajorShareholdersTextBlock?f={document_code}` | Jina Reader |
| 連結会社・親会社 | `irbank.net/{edinet_code}/af?f={document_code}` | Jina Reader |
| 従業員状況 | `irbank.net/{edinet_code}/notes/InformationAboutEmployeesTextBlock?f={document_code}` | Jina Reader |
| 沿革 | `irbank.net/{edinet_code}/history?f={document_code}` | Jina Reader |
| 設備状況 | `irbank.net/{edinet_code}/facilities?f={document_code}` | Jina Reader |

---

## 使用するTool

| Tool名 | 説明 |
|---|---|
| `fetch_with_jina(url)` | Jina Reader経由でページをMarkdown取得 |

> 取得したコンテンツはすべて `data/{ticker}/` にキャッシュとして保存し、LlamaIndexでインデックス化する

---

## CrewAI Agent定義

```python
# src/agents/agent1_yuho.py
from crewai import Agent
from src.tools.scraping_tools import JinaReaderTool

agent1 = Agent(
    role="有報リサーチャー",
    goal=(
        "有価証券報告書から企業の事業内容・リスク・大株主構造・従業員状況などの "
        "定性情報を網羅的に収集し、企業の本質的な姿を明らかにすること。"
    ),
    backstory=(
        "あなたは企業のIR資料を深く読み込む専門家です。"
        "有価証券報告書の各セクションから重要な情報を抽出し、"
        "投資判断に役立つ定性分析を提供することを得意としています。"
    ),
    tools=[JinaReaderTool()],
    llm=llm,  # DeepSeek v3
    verbose=True,
    max_iter=10,
)
```

---

## CrewAI Task定義

```python
# src/tasks/task1_yuho.py
from crewai import Task

task1 = Task(
    description=(
        "証券番号 {ticker} (EdinetCode: {edinet_code}, documentcode: {document_code}) の "
        "有価証券報告書から以下の情報をすべて収集してください:\n"
        "1. 事業内容とセグメント構成\n"
        "2. リスク情報（上位5件）: 各リスクについて、事業への影響度（大・中・小）を判定し、その根拠を簡潔に記述すること。判断にあたっては、利益率の高さやコスト構造（設備投資の重さ等）を考慮すること。\n"
        "3. 経営課題\n"
        "4. 研究開発の状況\n"
        "5. 大株主構成（上位10位）\n"
        "6. 親会社・連結会社の関係\n"
        "7. 従業員状況\n"
        "8. 会社沿革のハイライト\n"
        "9. 設備状況の概要\n\n"
        "各URLに1秒以上の間隔を空けてアクセスすること。"
    ),
    expected_output=(
        "上記9項目を網羅したMarkdown形式のレポート。\n"
        "各項目に見出しを付け、箇条書きや表を適宜使用すること。\n"
        "特に「リスク情報」については、以下のJSON形式を含めること:\n"
        "```json\n"
        "[\n"
        "  {\n"
        "    \"risk\": \"リスク項目名\",\n"
        "    \"impact\": \"大 or 中 or 小\",\n"
        "    \"reasoning\": \"影響度判定の具体的な根拠（例: 原価率が低いため赤字転落リスクは低い、設備コストが重いため台数減の打撃が大きい等）\"\n"
        "  }\n"
        "]\n"
        "```"
    ),
    agent=agent1,
)
```

---

## 注意事項

- 各URLへのアクセスは必ず1秒以上間隔を空けること
- document_codeはEdinet APIから最新の有報のものを使用すること
- 取得したMarkdownは `data/{ticker}/yuho_{section}.md` として保存すること
- LLMに情報の要約はさせてよいが、数値の計算はさせないこと
