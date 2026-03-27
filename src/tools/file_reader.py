"""
ファイル読み込みツール
RAGを使わずに全テキストをLLMのコンテキストにそのまま送るためのツール。
"""
import os
from loguru import logger
from crewai.tools import BaseTool
from pydantic import BaseModel


class MarkdownReadInput(BaseModel):
    filepath: str


class MarkdownReadTool(BaseTool):
    name: str = "MarkdownReadTool"
    description: str = (
        "指定されたMarkdownファイル全体を生データのまま読み込んで返す。"
        "filepathには 'data/7203/kessan_tansin.md' などの相対パスを指定すること。"
    )
    args_schema: type[BaseModel] = MarkdownReadInput

    def _run(self, filepath: str) -> str:
        try:
            if not os.path.exists(filepath):
                return f"ERROR: ファイルが見つかりません: {filepath}"
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            logger.info(f"ファイル読み込み成功: {filepath} ({len(content)} 文字)")
            return content
        except Exception as e:
            logger.error(f"ファイル読み込み失敗: {e}")
            return f"ERROR: ファイルの読み込みに失敗しました: {e}"
