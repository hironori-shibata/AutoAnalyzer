"""
AutoAnalyzer エントリーポイント
Slack Botを起動し、証券番号のメッセージを待受する。
"""
import sys
import os

# srcをインポートできるようにプロジェクトのルートディレクトリをパスに追加
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
load_dotenv()

from loguru import logger
from src.slack.bot import start_bot


if __name__ == "__main__":
    logger.info("AutoAnalyzer Bot 起動中...")
    start_bot()
