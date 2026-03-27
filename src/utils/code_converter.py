"""
証券番号（4桁）→ EdinetCode 変換ユーティリティ
data/edinet_code_list.csv (Edinet公式フォーマット・cp932エンコード) を使用する
"""
import os
import pandas as pd
from loguru import logger
from src.config import EDINET_CODE_LIST_CSV


def ticker_to_edinet_code(ticker: str) -> str | None:
    """
    4桁の証券番号から EdinetCode（E0XXXXX形式）に変換する。
    CSVが存在しない場合またはコードが見つからない場合は None を返す。
    """
    if not os.path.exists(EDINET_CODE_LIST_CSV):
        logger.error(
            f"Edinet コードリスト CSV が見つかりません: {EDINET_CODE_LIST_CSV}\n"
            "Edinet公式サイト (https://disclosure2.edinet-fsa.go.jp/weee0010.aspx) から "
            "EdinetcodeDlInfo.zip をダウンロードし、解凍したCSVを data/edinet_code_list.csv に配置してください。"
        )
        return None

    try:
        df = None
        for enc in ["shift_jis", "cp932", "utf-8"]:
            try:
                df = pd.read_csv(EDINET_CODE_LIST_CSV, encoding=enc, skiprows=1)
                break
            except UnicodeDecodeError:
                continue
        
        if df is None:
            logger.error("CSVファイルのエンコーディングを判別できませんでした（Shift-JIS, UTF-8のいずれでもありません）")
            return None
        # 証券コード列を探す（列名が全角の場合があるため柔軟に対応）
        code_col = None
        edinet_col = None
        for col in df.columns:
            if "証券" in col and "コード" in col:
                code_col = col
            if "EDINET" in col.upper() or "Ｅ" in col:
                edinet_col = col

        if code_col is None or edinet_col is None:
            logger.warning(f"CSV列名検出失敗。列一覧: {list(df.columns)}")
            # フォールバック: 位置ベースで取得（Edinet公式フォーマット想定）
            # 列: 0=EdinetCode, 1=開示者種別, 2=提出者種別, ...7=証券コード
            if len(df.columns) > 7:
                edinet_col = df.columns[0]
                code_col = df.columns[7]
            else:
                return None

        row = df[df[code_col].astype(str).str.strip().str.startswith(str(ticker))]
        if row.empty:
            logger.warning(f"証券番号 {ticker} が CSV に見つかりません")
            return None

        edinet_code = str(row.iloc[0][edinet_col]).strip()
        logger.info(f"証券番号 {ticker} → EdinetCode: {edinet_code}")
        return edinet_code

    except Exception as e:
        logger.error(f"EdinetCode変換エラー: {e}")
        return None
