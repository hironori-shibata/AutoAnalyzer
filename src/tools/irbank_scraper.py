"""
IR Bank スクレイパー
IR BankのresultsページからEdinetCodeを使って業績データを取得する。
複数年の財務テーブルをMarkdown形式で返す。
"""
import json
import math
import re
import time
from io import StringIO
from loguru import logger
from bs4 import BeautifulSoup
import pandas as pd
from crewai.tools import BaseTool
from pydantic import BaseModel

from src.tools.scraping_tools import safe_get
from src.config import IRBANK_BASE_URL


# ===== 日本語数値パーサー =====

def _parse_jp_value(s) -> float | None:
    """兆・億表記の文字列を float（円単位）に変換する。変換不能な値は None を返す。"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return None if math.isnan(s) else float(s)
    s = str(s).strip()
    if s in ('赤字', '-', '－', '', 'nan', 'NaN', '-'):
        return None

    sign = 1
    if s.startswith('-'):
        sign = -1
        s = s[1:]

    # "X兆Y億" パターン
    m = re.match(r'^([\d.]+)兆([\d.]+)億$', s)
    if m:
        return sign * (float(m.group(1)) * 1_000_000_000_000
                       + float(m.group(2)) * 100_000_000)

    # "X兆" パターン
    m = re.match(r'^([\d.]+)兆$', s)
    if m:
        return sign * float(m.group(1)) * 1_000_000_000_000

    # "X億" パターン
    m = re.match(r'^([\d.]+)億$', s)
    if m:
        return sign * float(m.group(1)) * 100_000_000

    # 純粋な数値
    try:
        return sign * float(s)
    except (ValueError, TypeError):
        return None


def _parse_table(df: pd.DataFrame, col_map: dict, confirmed_only: bool) -> list[dict]:
    """DataFrameを col_map に従って変換し、確定実績行のリストを返す。"""
    rows = []
    for _, row in df.iterrows():
        year = str(row.get('年度', '')).strip()
        # ヘッダー重複行・空行を除外
        if year in ('年度', '', 'nan', 'NaN'):
            continue
        # 予算・予測行を除外（確定実績のみモード）
        if confirmed_only and year.endswith('予'):
            continue
        record = {'year': year}
        for src_col, dst_key in col_map.items():
            record[dst_key] = _parse_jp_value(row.get(src_col))
        rows.append(record)
    return rows


class IRBankScraperInput(BaseModel):
    edinet_code: str
    section: str = "results"  # results / risk / task / rd / business など


class IRBankScraperTool(BaseTool):
    """
    IR BankからEdinetCodeを使って業績データ・有報セクション情報を取得する。
    resultsページから複数年の財務データをテーブル形式でパースして返す。
    """
    name: str = "IRBankScraperTool"
    description: str = (
        "IR BankからEdinetCodeを使って業績データを取得する。"
        "section='results' で複数年の財務データ（売上・利益・ROE等）をMarkdownテーブルで返す。"
        "edinet_code: EdinetCode（E0XXXXX形式）を指定すること。"
    )
    args_schema: type[BaseModel] = IRBankScraperInput

    def _run(self, edinet_code: str, section: str = "results") -> str:
        url = f"{IRBANK_BASE_URL}/{edinet_code}/{section}"
        logger.info(f"IR Bank スクレイピング: {url}")

        res = safe_get(url)
        if not res:
            return f"ERROR: {url} の取得に失敗しました"

        soup = BeautifulSoup(res.text, "html.parser")
        tables = soup.find_all("table")

        if not tables:
            # テーブルが見つからない場合はページテキストを返す
            body_text = soup.get_text(separator="\n", strip=True)
            return body_text[:10000] if body_text else "テーブルデータが見つかりませんでした"

        results = []
        for i, table in enumerate(tables[:5]):  # 最大5テーブル
            try:
                dfs = pd.read_html(StringIO(str(table)))
                if dfs:
                    results.append(f"### テーブル {i + 1}\n\n{dfs[0].to_markdown(index=False)}\n")
            except Exception as e:
                logger.warning(f"テーブル {i + 1} のパース失敗: {e}")

        return "\n".join(results) if results else "データの取得・パースに失敗しました"


# ===== IRBankFinancialTableTool =====

_PL_COLS = {
    '売上':   'revenue',
    '営利':   'operating_profit',
    '経常':   'ordinary_profit',
    '当期利益': 'net_income',
    '包括':   'comprehensive_income',
    'EPS':    'eps',
    'ROE':    'roe',
    'ROA':    'roa',
    '営利率':  'operating_margin',
    '原価率':  'cogs_ratio',
    '販管費率': 'sga_ratio',
}

_BS_COLS = {
    '総資産':     'total_assets',
    '純資産':     'net_assets',
    '株主資本':   'shareholders_equity',
    '自己資本比率': 'equity_ratio',
    '利益剰余金':  'retained_earnings',
    '有利子負債':  'interest_bearing_debt',
    '有利子負債比率': 'debt_ratio',
    'BPS':       'bps',
}

_CF_COLS = {
    '営業CF':      'operating_cf',
    '投資CF':      'investing_cf',
    '財務CF':      'financing_cf',
    'フリーCF':    'free_cf',
    '設備投資':    'capex',
    '現金等':      'cash',
    '営業CFマージン': 'operating_cf_margin',
}

_DIV_COLS = {
    '一株配当':    'dividend_per_share',
    '配当性向':    'payout_ratio',
    '剰余金の配当': 'total_dividend',
    '純資産配当率': 'div_on_equity',
    '自社株買い':  'buyback',
    '総還元額':    'total_return',
    '総還元性向':  'total_payout_ratio',
}


class IRBankFinancialTableInput(BaseModel):
    edinet_code: str
    confirmed_only: bool = True  # True = 確定通期実績のみ（「予」行を除外）


class IRBankFinancialTableTool(BaseTool):
    """
    IR BankのresultsページからEdinetCodeを使って複数年の業績数値を取得し、
    兆・億表記を実際の円単位（1円単位）に変換したJSONで返す。

    返却フィールド（confirmed_only=True がデフォルト）:
    - pl   : 損益 (revenue, operating_profit, net_income, eps, roe, roa, ... 単位:円/%)
    - bs   : 貸借対照表 (total_assets, shareholders_equity, equity_ratio, ... 単位:円/%)
    - cf   : キャッシュフロー (operating_cf, investing_cf, free_cf, capex, ... 単位:円/%)
    - dividend: 配当 (dividend_per_share, payout_ratio, total_dividend, ... 単位:円/%)

    free_cf は IR Bank の掲載値（営業CF + 投資CF）をそのまま返すため符号ミスが発生しない。
    investing_cf は通常マイナス値。
    monetary 値はすべて円（1円単位）。EPS/BPS は円/株。比率・マージンは %。
    """
    name: str = "IRBankFinancialTableTool"
    description: str = (
        "IR BankのresultsページからEdinetCodeを使って複数年の業績数値を取得し、"
        "兆・億表記を円単位に変換したJSONで返す。"
        "pl（損益）・bs（貸借）・cf（CF）・dividend（配当）の4セクションを含む。"
        "free_cfはIR Bank掲載値（営業CF＋投資CF済み）のためFCF符号ミスが起きない。"
        "monetary値はすべて円（1円単位）。EPS/BPSは円/株。比率・マージンは%。"
        "edinet_code: EdinetCode（E0XXXXX形式）。"
        "confirmed_only=True（デフォルト）で確定通期実績のみ返す。"
    )
    args_schema: type[BaseModel] = IRBankFinancialTableInput

    def _run(self, edinet_code: str, confirmed_only: bool = True) -> str:
        url = f"{IRBANK_BASE_URL}/{edinet_code}/results"
        logger.info(f"IR Bank 数値テーブル取得: {url}")

        res = safe_get(url)
        if not res:
            return json.dumps({"error": f"{url} の取得に失敗しました"}, ensure_ascii=False)

        try:
            tables = pd.read_html(StringIO(res.text))
        except Exception as e:
            return json.dumps({"error": f"テーブルパース失敗: {e}"}, ensure_ascii=False)

        if len(tables) < 3:
            return json.dumps({"error": f"テーブル数が不足しています（{len(tables)}個）"}, ensure_ascii=False)

        result: dict = {
            "unit_note": (
                "monetary values: yen (円, 1円単位). "
                "EPS/BPS: yen per share. "
                "ROE/ROA/margins/ratios: percent (%). "
                "free_cf = operating_cf + investing_cf (IR Bank pre-computed, no sign error). "
                "investing_cf is usually negative."
            ),
            "pl":       _parse_table(tables[0], _PL_COLS,  confirmed_only),
            "bs":       _parse_table(tables[1], _BS_COLS,  confirmed_only),
            "cf":       _parse_table(tables[2], _CF_COLS,  confirmed_only),
        }
        if len(tables) >= 4:
            result["dividend"] = _parse_table(tables[3], _DIV_COLS, confirmed_only)

        return json.dumps(result, ensure_ascii=False, indent=2)
