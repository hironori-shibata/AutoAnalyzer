# AutoAnalyzer 設計書 — インデックス

Slackに4桁の証券番号を入力するだけで、複数のAI Agentが協調して企業価値分析レポートを生成・送信するシステムの設計書一覧です。

---

## 設計書ファイル構成

| ファイル | 内容 |
|---|---|
| [architecture.md](./architecture.md) | システム全体アーキテクチャ・フロー |
| [tech_stack.md](./tech_stack.md) | 技術スタック・依存ライブラリ |
| [directory_structure.md](./directory_structure.md) | ディレクトリ・ファイル構成 |
| [data_sources.md](./data_sources.md) | 外部データリソース一覧 |
| [slack_integration.md](./slack_integration.md) | Slack連携仕様 |
| [agents/agent1_yuho_researcher.md](./agents/agent1_yuho_researcher.md) | Agent1: 有報リサーチャー |
| [agents/agent2_rival_researcher.md](./agents/agent2_rival_researcher.md) | Agent2: ライバルリサーチャー |
| [agents/agent3_kessan_researcher.md](./agents/agent3_kessan_researcher.md) | Agent3: 最新決算短信リサーチャー |
| [agents/agent4_performance_researcher.md](./agents/agent4_performance_researcher.md) | Agent4: 業績リサーチャー |
| [agents/agent5_stock_researcher.md](./agents/agent5_stock_researcher.md) | Agent5: 株価・需給リサーチャー |
| [agents/agent6_manager.md](./agents/agent6_manager.md) | Agent6: 統括マネージャー（ボス） |
| [tools/calculation_tools.md](./tools/calculation_tools.md) | Python計算ツール仕様 |
| [tools/scraping_tools.md](./tools/scraping_tools.md) | Webスクレイピングツール仕様 |

---

## 実装順序（推奨）

```
1. directory_structure.md  → プロジェクト雛形の作成
2. tech_stack.md           → 環境構築・依存関係インストール
3. data_sources.md         → データ取得の動作確認
4. tools/                  → 計算・スクレイピングツール実装
5. agents/ (1〜5)          → 各リサーチャーAgent実装
6. agents/agent6           → 統括マネージャー実装
7. slack_integration.md    → Slack送受信実装
8. architecture.md         → 結合テスト・全体フロー確認
```

---

## 重要な制約事項（全Agentに適用）

- **LLMに計算をさせない**。数値計算は必ずPython Toolに委譲すること
- **Webスクレイピング時は必ず1秒以上のウェイトを挿入**すること
- **信用倍率の解釈に注意**: 「高い＝良い」ではなく、過剰な買い残は将来の売り圧力（ネガティブ）を意味する。また、**信用倍率の低下は需給の「改善」**、上昇は「悪化」として解釈すること
- 単一時点の数値ではなく**時系列変化**を分析の軸とすること
