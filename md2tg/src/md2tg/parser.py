from markdown_it import MarkdownIt
from markdown_it.token import Token
from typing import List

class MarkdownParser:
    def __init__(self):
        # Initialize with GFM-like settings which includes tables and strikethrough
        # Enable HTML to support tags like <u>, <tg-spoiler> injected by entity converter
        self.md = MarkdownIt("gfm-like", {"html": True})
        
    def parse(self, text: str) -> List[Token]:
        """
        Parse raw markdown text into a list of tokens.
        This layer is strictly for parsing, no logic applied.
        """
        return self.md.parse(text)
