from dataclasses import dataclass, field
from typing import List, Optional, Union
from enum import Enum

class TextStyle(Enum):
    BOLD = "bold"
    ITALIC = "italic"
    STRIKETHROUGH = "strikethrough"
    UNDERLINE = "underline"
    SPOILER = "spoiler"
    CODE = "code"
    PRE = "pre"  # For preformatted blocks inside text, though usually CodeBlock is better
    URL = "url"  # Special case for links

@dataclass
class TextNode:
    """Basic text unit with styling."""
    content: str
    styles: List[TextStyle] = field(default_factory=list)
    url: Optional[str] = None  # Only used if TextStyle.URL is present

@dataclass
class BaseBlock:
    """Base class for all block-level elements."""
    pass

@dataclass
class Paragraph(BaseBlock):
    children: List[TextNode] = field(default_factory=list)

@dataclass
class Heading(BaseBlock):
    level: int  # 1-6
    children: List[TextNode] = field(default_factory=list)

@dataclass
class Quote(BaseBlock):
    children: List[BaseBlock] = field(default_factory=list)

@dataclass
class CodeBlock(BaseBlock):
    content: str
    language: Optional[str] = None

@dataclass
class ListItem(BaseBlock):
    children: List[BaseBlock] = field(default_factory=list)

@dataclass
class ListBlock(BaseBlock):
    ordered: bool
    items: List[ListItem] = field(default_factory=list)

@dataclass
class TableCell(BaseBlock):
    children: List[TextNode] = field(default_factory=list)
    header: bool = False
    align: Optional[str] = None  # left, center, right

@dataclass
class TableRow(BaseBlock):
    cells: List[TableCell] = field(default_factory=list)

@dataclass
class Table(BaseBlock):
    rows: List[TableRow] = field(default_factory=list)

@dataclass
class Document:
    blocks: List[BaseBlock] = field(default_factory=list)
