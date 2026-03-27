# システム全体アーキテクチャ設計書

## 概要

Slackから証券番号を受け取り、6つのAI Agentが逐次協調して企業価値分析レポートを生成し、Slackへ返送するシステム。

---

## システムフロー

```
[ユーザー]
    │  証券番号(4桁)をSlackに入力
    ▼
[Slack Bot (slack_integration)]
    │  証券番号を受信・バリデーション
    │  ThreadPoolExecutor でバックグラウンド実行
    ▼
[Orchestrator (crew.py: run_analysis())]
    │  EdinetCode変換 → documentcode取得 → CrewAIのCrew起動
    │
    ├──[Agent1: 有報リサーチャー]
    │     IR Bankから有報データ（リスク・事業内容・大株主等）取得
    │
    ├──[Agent2: ライバルリサーチャー]
    │     DuckDuckGOで競合情報 + EV/EBITDA検索
    │     株探・株予報proから競合PER取得
    │
    ├──[Agent3: 最新決算短信リサーチャー]
    │     IR Bank → PDF取得 → doclingでMD変換
    │     MarkdownReadTool で生データ直読み
    │     FinancialCalcTool で財務指標計算
    │     セグメント別業績・配当情報も抽出
    │
    ├──[Agent4: 業績リサーチャー]
    │     IR Bankから複数年データ取得
    │     TrendAnalysisTool で時系列トレンド計算
    │     配当・配当性向のトレンドも把握
    │
    ├──[Agent5: 株価・需給リサーチャー]
    │     株探・株予報pro・空売り.net・IR Bankから取得
    │     信用倍率・空売り比率の時系列分析
    │
    └──[Agent6: 統括マネージャー] ← 上記5 Agentの結果を context で集約
          MarkdownReadTool で生データ補完
          DCFValuationTool でDCF計算
          MultiplesValuationTool でPER/EV/EBITDA計算
          WACCは自己資本比率から算出した負債比率を使用
          総合企業価値評価レポート生成
                │
                ▼
    [Slack Bot]
          レポートをSlackへ送信
    [ユーザー]
```

---

## Agentの実行戦略（CrewAI）

| フェーズ | Agent | 実行方式 | 依存関係 |
|---|---|---|---|
| Phase 1 | Agent1〜5 | **逐次実行** (sequential) | なし |
| Phase 2 | Agent6 | **逐次実行** (sequential) | context=[task1〜task5] |

> **注意:** CrewAI の `Process.sequential` を使用し、Agent6は`context`引数でAgent1〜5の全結果を参照する。
> （Agent1〜5は並行して動くわけではないが、Agent6が必ず最後に実行される。）

```python
crew = Crew(
    name=f"AutoAnalyzer_{ticker}",
    agents=[agent1, agent2, agent3, agent4, agent5, agent6],
    tasks=[task1, task2, task3, task4, task5, task6],
    process=Process.sequential,
    verbose=True,
    output_log_file=f"data/{ticker}/crew_execution.log",
)
```

---

## データの流れ

```
証券番号(4桁)
    │
    ├─→ EdinetCode変換 (data/edinet_code_list.csv CSVルックアップ)
    │         ↓
    │   Edinet API → documentcode取得
    │
    ├─→ IR Bank URL生成
    │         irbank.net/{EdinetCode}/results     (複数年業績)
    │         irbank.net/{EdinetCode}/risk?f=...  (リスク情報)
    │         irbank.net/{EdinetCode}/business?... (事業内容)
    │
    ├─→ 決算短信URL取得・変換
    │         irbank.net/td/search?q={ticker}
    │         → PDFダウンロード → docling → Markdown
    │         → data/{ticker}/kessan_tansin.md に保存
    │         → Agent3がMarkdownReadToolで直接読み込む
    │
    └─→ DuckDuckGO Web検索
              EV/EBITDA業界平均・競合情報 (Agent2が使用)
              中国語サイト(zhihu.com等)はNGドメインフィルタで自動除外
```

> **廃止:** LlamaIndex (RAGインデックス) は廃止済み。
> Agent がデータファイルを直接 MarkdownReadTool で読み込む方式に変更。

---

## エラーハンドリング方針

| エラー種別 | 対処方針 |
|---|---|
| スクレイピング失敗 | リトライ3回 → スキップしてAgent6に「データ取得失敗」を通知 |
| PDF変換失敗 | エラーログ記録 → レポートに「変換失敗」と記載 |
| Edinet API障害 | フォールバック: IR Bankから直接取得を試みる |
| LLM APIタイムアウト | タイムアウト400秒 → リトライ |
| 証券番号が無効 | Slack即時エラー返信 |
| CAGR計算（負の数） | TrendAnalysisTool内部でNone扱い・スキップ（複素数エラー防止） |
| 単位ズレ（百万円） | DCF/MultiplesツールでEV < 株数*10 の場合に自動で100万倍補正 |

---

## 出力レポート構成（Agent6生成）

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
## 8. 投資判断サマリー
```

---

## 関連ファイル

- 実装起点: `src/main.py`
- Crew定義: `src/crew.py`
- Agent定義: `src/agents/`
- Tool定義: `src/tools/`
- 実行ログ: `data/{ticker}/crew_execution.log`（実行ごとに上書き）
