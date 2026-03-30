# AutoAnalyzer

## Project Overview
AutoAnalyzer is a Python-based intelligent system that leverages multiple AI agents to generate comprehensive corporate valuation reports. By simply inputting a 4-digit stock ticker code into a Slack channel, the system orchestrates a team of specialized agents using the **CrewAI** framework. These agents gather qualitative and quantitative data from various sources (such as EDINET, financial results, competitor data, and news), perform financial calculations, and synthesize a final investment judgment report.

### Key Technologies
*   **Language:** Python 3.11+
*   **AI/Orchestration:** CrewAI, LangChain, LiteLLM
*   **Data Fetching & Scraping:** Requests, BeautifulSoup4, DuckDuckGo Search, Docling
*   **Data Processing:** Pandas, NumPy
*   **Integration:** Slack Bolt, Slack SDK (for bot interaction)

### Agent Architecture
The system employs a sequential multi-agent workflow:
*   **Agent 1 (Yuho):** Analyzes Securities Reports (Yuka Shoken Hokokusho) for qualitative information.
*   **Agent 2/2a (Rival):** Gathers quantitative and qualitative data on competitors and industry structure.
*   **Agent 3 (Kessan):** Fetches the latest financial results and calculates financial indicators.
*   **Agent 4 (Performance):** Analyzes multi-year performance trends.
*   **Agent 5 (Stock):** Analyzes stock price and supply/demand dynamics.
*   **Agent News:** Collects industry and geopolitical news starting from the company's sector.
*   **Agent 6 (Manager):** Aggregates data, calculates corporate value (DCF, Multiples), and generates the main report.
*   **Agent 7 (Critic):** Challenges Agent 6's report from a critical perspective.
*   **Agent 8 (Investor):** Reviews all reports and makes the final investment judgment.

## Building and Running

### Prerequisites
*   Anaconda (conda) installed.
*   Python 3.11 or higher.

### Setup Instructions
1.  **Environment Creation:**
    ```bash
    conda create -n autoanalyzer python=3.11
    conda activate autoanalyzer
    pip install -r requirements.txt
    ```
2.  **Data Preparation:** Download `EdinetcodeDlInfo.zip` from the EDINET official site, extract the CSV, and place it at `data/edinet_code_list.csv`.
3.  **Environment Variables:** Copy `.env.example` to `.env` and fill in the required API keys (DeepSeek, Slack Bot/App tokens, EDINET API key, OpenAI API key).
4.  **Slack App Configuration:** Ensure Socket Mode is enabled and appropriate scopes (`chat:write`, `files:write`, etc.) and Event Subscriptions are configured in the Slack App console.

### Execution
Start the Slack bot by running:
```bash
conda activate autoanalyzer
python src/main.py
```
Once running, send a 4-digit ticker code (e.g., `7203`) to the configured Slack channel to trigger the analysis.

## Development Conventions & Constraints
*   **Delegation of Calculations:** LLMs must *never* perform complex numerical calculations directly. They should always delegate mathematical operations to dedicated Python tools (`src/tools/financial_calc.py`, etc.).
*   **Scraping Etiquette:** Always insert a wait/sleep time of at least 1 second between scraping requests to avoid overloading target servers.
*   **Analytical Focus:** Analysis should prioritize **time-series changes** and trends rather than relying solely on single-point-in-time metrics.
*   **Interpretation Nuances:** Be aware of specific financial interpretations (e.g., a high margin buying ratio is not automatically "good").
*   **Logging:** The system uses `loguru` for robust logging, and CrewAI events are captured in JSONL format under the `data/{ticker}/` directory for detailed auditing.
