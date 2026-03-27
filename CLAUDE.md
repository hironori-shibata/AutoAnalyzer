# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

AutoAnalyzer is a Japanese corporate valuation analysis system triggered via Slack. A user sends a 4-digit stock ticker (e.g., "7203") and 6 AI agents collaborate sequentially to produce a comprehensive valuation report in Markdown.

## Setup & Run

```bash
# Setup (Python 3.11 required)
conda create -n autoanalyzer python=3.11
conda activate autoanalyzer
pip install -r requirements.txt
cp .env.example .env  # then fill in API keys

# Run
python src/main.py
```

Required `.env` keys: `DEEPSEEK_API_KEY`, `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `SLACK_SIGNING_SECRET`, `EDINET_API_KEY`

Also requires `data/edinet_code_list.csv` — download `EdinetcodeDlInfo.zip` from the Edinet official disclosure site and extract the CSV there.

## Architecture

**Entry point:** `src/main.py` starts the Slack bot in Socket Mode.

**Analysis pipeline** (`src/crew.py::run_analysis(ticker)`):
1. Converts ticker → EdinetCode via `data/edinet_code_list.csv` lookup
2. Fetches `documentcode` from the Edinet API
3. Builds 6 tasks and runs them via `crewai.Crew(process=Process.sequential)`
4. Sends final Markdown report to Slack via `src/slack/sender.py`

**Agents** (`src/agents/`) run in order:
- `agent1_yuho` — Qualitative data from securities reports (IR Bank + Jina Reader)
- `agent2_rival` — Competitor/industry analysis (DuckDuckGO + web scraping)
- `agent3_kessan` — Latest earnings brief (IR Bank PDF → docling → Markdown)
- `agent4_performance` — Multi-year performance trends (IR Bank historical data)
- `agent5_stock` — Stock price & demand metrics (kabutan, karauri.net)
- `agent6_manager` — Aggregates all prior outputs (`context=[task1...task5]`), runs DCF + multiples valuation, produces final report

**Tasks** (`src/tasks/`) define what each agent must accomplish. Task6 uses `context` to receive all previous task outputs.

**Tools** (`src/tools/`) are deterministic Python functions (no LLM math):
- `financial_calc.py` — Financial metrics (ROE, ROA, margins, etc.)
- `valuation_calc.py` — DCF and multiples (PER, EV/EBITDA) valuation
- `edinet_client.py` — Edinet API client
- `kessan_fetcher.py` — Earnings brief PDF fetcher
- `irbank_scraper.py` — IR Bank web scraper
- `stock_scraper.py`, `scraping_tools.py` — Stock/web scrapers
- `web_search.py` — DuckDuckGO search
- `file_reader.py` — Direct Markdown file reader

**LLM:** DeepSeek v3 via OpenAI-compatible endpoint, configured in `src/config.py`.

## Key Design Rules

- **No LLM math:** All numerical calculations must use Python tool functions, never rely on the LLM to compute values.
- **Web scraping delays:** Enforce ≥1 second between requests.
- **Unit handling:** DCF/multiples tools auto-detect and correct million-yen vs. yen mismatches.
- **PDF processing:** docling converts PDFs → Markdown; agents read the file directly (no RAG/embeddings).
- **Error handling:** Failed data sources should be skipped gracefully; Agent6 should be notified of any gaps.
- **Signal interpretation (stock demand):** High credit ratio = excess buying pressure (negative signal); decreasing credit ratio = demand improvement (positive signal).

## Output

Reports are saved to `data/{ticker}/` and uploaded to the Slack thread. Logs are written to `data/{ticker}/crew_execution.log`.

## Documentation

Detailed specs in `doc/`: `architecture.md`, `tech_stack.md`, `data_sources.md`, `slack_integration.md`, per-agent docs in `doc/agents/`, and tool docs in `doc/tools/`.
