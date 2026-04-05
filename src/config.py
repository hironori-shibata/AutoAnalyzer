"""
設定・定数管理モジュール
DeepSeek LLMインスタンスの生成と共通定数を管理する
"""
import os
from dotenv import load_dotenv
from crewai import LLM

load_dotenv()

# ===== LLM設定 =====
def get_llm() -> LLM:
    """DeepSeek v3 LLMインスタンスを返す（CrewAI 1.0+ LiteLLM対応）"""
    return LLM(
        model="openai/deepseek-chat",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
        temperature=0.2,
        timeout=400,
        max_tokens=8192,
    )

def get_llm_long_output() -> LLM:
    """長文出力が必要なAgent（Agent6等）向け。max_tokensを8192に設定してレポート途切れを防ぐ。"""
    return LLM(
        model="openai/deepseek-chat",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
        temperature=0.2,
        timeout=600,
        max_tokens=8192,
    )

def get_reasoner_llm() -> LLM:
    """DeepSeek Reasoner (R1) LLMインスタンスを返す"""
    return LLM(
        model="openai/deepseek-reasoner",
        api_key=os.environ["DEEPSEEK_API_KEY"],
        base_url="https://api.deepseek.com",
        timeout=400,
    )

def get_perplexity_llm() -> LLM:
    """Perplexity Sonar (OpenRouter経由) LLMインスタンスを返す。
    sonarはウェブ検索を内蔵しているため、外部検索ツール不要。"""
    return LLM(
        model="openrouter/perplexity/sonar",
        api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0.2,
        timeout=400,
        max_tokens=8192,
    )

def get_gemini_llm() -> LLM:
    """Google Gemini Flash (公式API) LLMインスタンスを返す。
    Google Search Grounding による最新ウェブ情報収集に対応。
    モデル名は環境に合わせて GEMINI_MODEL 環境変数で上書き可能。
    デフォルト: gemini-2.0-flash（要 GOOGLE_API_KEY）"""
    model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    return LLM(
        model=f"gemini/{model}",
        api_key=os.environ["GOOGLE_API_KEY"],
        temperature=0.2,
        timeout=400,
    )

def get_chatgpt_llm() -> LLM:
    """ChatGPT 5.4 (OpenRouter経由) LLMインスタンスを返す。Agent7反論エージェント用。"""
    return LLM(
        model="openrouter/openai/gpt-5.4-mini",
        api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0.3,
        timeout=400,
        max_tokens=4096,
    )

# ===== デバッグ設定 =====
# DEBUG_MODE=true にすると、各エージェントの中間出力をリアルタイムでSlackに送信する。
# .env または環境変数で切り替え可能。
DEBUG_MODE: bool = os.environ.get("DEBUG_MODE", "false").lower() == "true"

# ===== 共通定数 =====
DATA_DIR = "data"
EDINET_CODE_LIST_CSV = os.path.join(DATA_DIR, "edinet_code_list.csv")

# スクレイピング設定
REQUEST_TIMEOUT = 30       # HTTPタイムアウト（秒）
REQUEST_RETRIES = 3        # リトライ回数
REQUEST_SLEEP = 1.0        # リクエスト間隔（秒）
PDF_CONVERT_TIMEOUT = 120  # PDF変換タイムアウト（秒）

# Jina Reader
JINA_BASE_URL = "https://r.jina.ai/"
JINA_MAX_CHARS = 50000     # 取得テキストの最大文字数

# IR Bank
IRBANK_BASE_URL = "https://irbank.net"

# Edinet API
EDINET_API_URL = "https://api.edinet-fsa.go.jp/api/v2/documents.json"
EDINET_DOC_TYPE_YUHO = 120  # 有価証券報告書

# DCFデフォルトパラメータ
DCF_DEFAULTS = {
    "risk_free_rate": 0.016,        # 日本10年国債利回り（2026年時点, BOJ正常化後）
    "equity_risk_premium": 0.055,   # 株式リスクプレミアム（Damodaran Japan ERP準拠: 4.5〜5.5%）
    "beta": 1.1,                    # デフォルトβ（業種不明時のフォールバック）
    "debt_cost": 0.01,              # 負債コスト基準値（時価総額連動で自動調整される）
    "debt_ratio": 0.3,              # 有利子負債比率（D/(D+E)、市場価値ベース推奨）
    "tax_rate": 0.30,              # 実効税率
    "capex_ratio": 0.06,           # 設備投資比率（売上比）
    "terminal_growth_rate": 0.007,  # 永久成長率（1%に変更）
    "projection_years": 7,         # 予測期間（年）※5→7に変更（TV依存度低減のため）
}
