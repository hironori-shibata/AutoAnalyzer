"""
設定・定数管理モジュール
全LLMはOpenRouter経由で統一。モデルは.envの環境変数で自由に切り替え可能。
レートリミット時はOpenRouterのfallbackルーティングで自動的に次候補へ切り替わる。
"""
import os
from dotenv import load_dotenv
from crewai import LLM

load_dotenv()

# ===== LLM設定 =====
# 全モデルはOpenRouter BYOKで統一。各変数のデフォルト値は.env.exampleを参照。

def _build_extra_body(primary: str, fallbacks_env_key: str) -> dict | None:
    """
    OpenRouterのfallbackルーティング用extra_bodyを構築する。
    fallbacks_env_keyに対応する環境変数がカンマ区切りでフォールバックモデルを持つ場合のみ設定。
    例: OPENROUTER_DEFAULT_FALLBACKS=google/gemini-flash-1.5,openai/gpt-4o-mini
    """
    raw = os.environ.get(fallbacks_env_key, "").strip()
    if not raw:
        return None
    fallbacks = [m.strip() for m in raw.split(",") if m.strip()]
    if not fallbacks:
        return None
    return {
        "models": [primary] + fallbacks,
        "route": "fallback",
    }

def get_llm() -> LLM:
    """汎用LLM（Agent1/3a/4/5用）"""
    primary = os.environ.get("OPENROUTER_DEFAULT_MODEL")
    extra_body = _build_extra_body(primary, "OPENROUTER_DEFAULT_FALLBACKS")
    return LLM(
        model=f"openrouter/{primary}",
        api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0.2,
        timeout=800,
        max_tokens=8192*2,
        **({"extra_body": extra_body} if extra_body else {}),
    )

def get_llm_long_output() -> LLM:
    """長文出力LLM（Agent7: 最終レポート生成用）"""
    primary = os.environ.get("OPENROUTER_LONG_MODEL")
    extra_body = _build_extra_body(primary, "OPENROUTER_LONG_FALLBACKS")
    return LLM(
        model=f"openrouter/{primary}",
        api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0.2,
        timeout=800,
        max_tokens=8192*2,
        **({"extra_body": extra_body} if extra_body else {}),
    )

def get_reasoner_llm() -> LLM:
    """推論特化LLM（Agent3/9: 競合分析・投資家分析用）"""
    primary = os.environ.get("OPENROUTER_REASONER_MODEL")
    extra_body = _build_extra_body(primary, "OPENROUTER_REASONER_FALLBACKS")
    return LLM(
        model=f"openrouter/{primary}",
        api_key=os.environ["OPENROUTER_API_KEY"],
        timeout=600,
        max_tokens=8192*2,
        **({"extra_body": extra_body} if extra_body else {}),
    )

def get_perplexity_llm() -> LLM:
    """Web検索内蔵LLM（Agent3: 競合・業界調査用）"""
    primary = os.environ.get("OPENROUTER_SEARCH_MODEL")
    extra_body = _build_extra_body(primary, "OPENROUTER_SEARCH_FALLBACKS")
    return LLM(
        model=f"openrouter/{primary}",
        api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0.2,
        timeout=400,
        max_tokens=8192*2,
        **({"extra_body": extra_body} if extra_body else {}),
    )

def get_gemini_llm() -> LLM:
    """ディープリサーチLLM（Agent2: 対象企業調査用）"""
    primary = os.environ.get("OPENROUTER_GEMINI_MODEL")
    extra_body = _build_extra_body(primary, "OPENROUTER_GEMINI_FALLBACKS")
    return LLM(
        model=f"openrouter/{primary}",
        api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0.2,
        timeout=400,
        max_tokens=8192*2,
        **({"extra_body": extra_body} if extra_body else {}),
    )

def get_chatgpt_llm() -> LLM:
    """批評LLM（Agent8: バリュエーション批評・反論用）"""
    primary = os.environ.get("OPENROUTER_CRITIC_MODEL")
    extra_body = _build_extra_body(primary, "OPENROUTER_CRITIC_FALLBACKS")
    return LLM(
        model=f"openrouter/{primary}",
        api_key=os.environ["OPENROUTER_API_KEY"],
        temperature=0.3,
        timeout=400,
        max_tokens=4096,
        **({"extra_body": extra_body} if extra_body else {}),
    )

# ===== デバッグ設定 =====
# DEBUG_MODE=true にすると各エージェントの中間出力をリアルタイムでSlackに送信する
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
    "tax_rate": 0.30,               # 実効税率
    "capex_ratio": 0.06,            # 設備投資比率（売上比）
    "terminal_growth_rate": 0.007,  # 永久成長率
    "projection_years": 7,          # 予測期間（年）
}
