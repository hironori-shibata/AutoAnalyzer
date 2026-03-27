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
    "risk_free_rate": 0.015,        # 日本10年国債利回り
    "equity_risk_premium": 0.06,  # 株式リスクプレミアム
    "beta": 1.1,                   # デフォルトベータ
    "debt_cost": 0.01,             # 負債コスト
    "debt_ratio": 0.3,             # 負債比率
    "tax_rate": 0.30,              # 実効税率
    "capex_ratio": 0.06,           # 設備投資比率（売上比）
    "terminal_growth_rate": 0.007,  # 永久成長率（1%に変更）
    "projection_years": 7,         # 予測期間（年）※5→7に変更（TV依存度低減のため）
}
