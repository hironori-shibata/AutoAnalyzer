"""
Edinet API クライアント
Edinet APIから最新の有価証券報告書のdocumentcode（docID）を取得する。
"""
import re
import time
import requests
from loguru import logger

def get_document_code(edinet_code: str, doc_type_code: int = 120) -> str | None:
    """
    IR Bankから最新の有価証券報告書のdocumentcode（docID）を取得する。
    （Edinet APIは過去365日を1日ずつ探索する必要がありタイムアウトするため、IR Bankを利用）

    Args:
        edinet_code: EdinetCode（E0XXXXX形式）
        doc_type_code: 書類種別コード（※現在は120固定を想定）

    Returns:
        docID（文字列）または None
    """
    url = f"https://irbank.net/{edinet_code}"
    headers = {"User-Agent": "Mozilla/5.0"}

    try:
        time.sleep(1)  # レートリミット対策
        res = requests.get(url, headers=headers, timeout=30)
        if res.status_code != 200:
            logger.error(f"IR Bank 接続エラー ({res.status_code})")
            return None

        # 有価証券報告書のdocIDは通常 S100XXXX 等の形式
        match = re.search(r'f=(S[0-9A-Z]{7})', res.text)
        if match:
            doc_id = match.group(1)
            logger.info(f"documentcode取得 (IR Bank): {edinet_code} → {doc_id}")
            return doc_id
        else:
            logger.warning(f"documentcode が見つかりませんでした: {edinet_code}")
            return None

    except Exception as e:
        logger.error(f"IR Bank スクレイピングエラー ({edinet_code}): {e}")
        return None
