"""md2tg — Convert Markdown to Telegram-compatible HTML."""

from .ast_nodes import (
    BaseBlock,
    CodeBlock,
    Document,
    Heading,
    ListBlock,
    ListItem,
    Paragraph,
    Quote,
    Table,
    TableCell,
    TableRow,
    TextNode,
    TextStyle,
)
from .parser import MarkdownParser
from .renderer import TelegramRenderer
from .splitter import MessageSplitter
from .transformer import ASTTransformer

__all__ = [
    # High-level
    "convert",
    # Pipeline components
    "MarkdownParser",
    "ASTTransformer",
    "TelegramRenderer",
    "MessageSplitter",
    # AST nodes
    "Document",
    "BaseBlock",
    "Heading",
    "Paragraph",
    "Quote",
    "CodeBlock",
    "ListBlock",
    "ListItem",
    "Table",
    "TableRow",
    "TableCell",
    "TextNode",
    "TextStyle",
]

# Singleton instances used by the convenience helper
_parser = MarkdownParser()
_transformer = ASTTransformer()
_renderer = TelegramRenderer()
_splitter = MessageSplitter(_renderer)


def convert(markdown: str) -> list[str]:
    """Convert a Markdown string to a list of Telegram-compatible HTML parts.

    Each part is guaranteed to be ≤ 4 096 characters so it can be sent
    as a single Telegram message.
    """
    tokens = _parser.parse(markdown)
    doc = _transformer.transform(tokens)
    return _splitter.split(doc)
