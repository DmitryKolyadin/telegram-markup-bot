"""Tests for the md2tg library."""

import pytest
from md2tg import (
    convert,
    MarkdownParser,
    ASTTransformer,
    TelegramRenderer,
    MessageSplitter,
    Document,
    Heading,
    Paragraph,
    CodeBlock,
    ListBlock,
    Quote,
    Table,
    TextNode,
    TextStyle,
)


# ---------------------------------------------------------------------------
# High-level convert() helper
# ---------------------------------------------------------------------------

class TestConvert:
    def test_simple_bold(self):
        parts = convert("**bold**")
        assert len(parts) == 1
        assert "<b>bold</b>" in parts[0]

    def test_simple_italic(self):
        parts = convert("*italic*")
        assert len(parts) == 1
        assert "<i>italic</i>" in parts[0]

    def test_bold_and_italic(self):
        parts = convert("**bold** and *italic*")
        assert "<b>bold</b>" in parts[0]
        assert "<i>italic</i>" in parts[0]

    def test_strikethrough(self):
        parts = convert("~~strike~~")
        assert "<s>strike</s>" in parts[0]

    def test_inline_code(self):
        parts = convert("`code`")
        assert "<code>code</code>" in parts[0]

    def test_fenced_code_block(self):
        md = "```python\nprint('hello')\n```"
        parts = convert(md)
        assert '<pre><code class="language-python">' in parts[0]
        assert "print(&#x27;hello&#x27;)" in parts[0]

    def test_fenced_code_block_no_lang(self):
        md = "```\nsome code\n```"
        parts = convert(md)
        assert "<pre><code>" in parts[0]

    def test_heading(self):
        parts = convert("# Title")
        assert "<b>Title</b>" in parts[0]

    def test_blockquote(self):
        parts = convert("> quoted text")
        assert "<blockquote>" in parts[0]
        assert "quoted text" in parts[0]
        assert "</blockquote>" in parts[0]

    def test_unordered_list(self):
        md = "- item 1\n- item 2"
        parts = convert(md)
        assert "• item 1" in parts[0]
        assert "• item 2" in parts[0]

    def test_ordered_list(self):
        md = "1. first\n2. second"
        parts = convert(md)
        assert "1. first" in parts[0]
        assert "2. second" in parts[0]

    def test_link(self):
        parts = convert("[text](https://example.com)")
        assert '<a href="https://example.com">text</a>' in parts[0]

    def test_table(self):
        md = "| A | B |\n|---|---|\n| 1 | 2 |"
        parts = convert(md)
        assert "<pre>" in parts[0]
        assert "A" in parts[0]
        assert "B" in parts[0]

    def test_empty_input(self):
        parts = convert("")
        assert parts == [] or parts == [""]

    def test_multiple_paragraphs(self):
        md = "First paragraph.\n\nSecond paragraph."
        parts = convert(md)
        assert "First paragraph." in parts[0]
        assert "Second paragraph." in parts[0]

    def test_html_escaping(self):
        parts = convert("Use 5 > 3 & \"quotes\"")
        text = parts[0]
        assert "&amp;" in text
        assert "&quot;quotes&quot;" in text


# ---------------------------------------------------------------------------
# Pipeline components
# ---------------------------------------------------------------------------

class TestParser:
    def test_returns_tokens(self):
        parser = MarkdownParser()
        tokens = parser.parse("**hello**")
        assert len(tokens) > 0

    def test_empty_returns_empty(self):
        parser = MarkdownParser()
        tokens = parser.parse("")
        assert tokens == [] or len(tokens) == 0


class TestTransformer:
    def test_builds_document(self):
        parser = MarkdownParser()
        transformer = ASTTransformer()
        tokens = parser.parse("# Title\n\nParagraph")
        doc = transformer.transform(tokens)
        assert isinstance(doc, Document)
        assert len(doc.blocks) == 2
        assert isinstance(doc.blocks[0], Heading)
        assert isinstance(doc.blocks[1], Paragraph)

    def test_code_block(self):
        parser = MarkdownParser()
        transformer = ASTTransformer()
        tokens = parser.parse("```py\ncode\n```")
        doc = transformer.transform(tokens)
        assert any(isinstance(b, CodeBlock) for b in doc.blocks)
        cb = [b for b in doc.blocks if isinstance(b, CodeBlock)][0]
        assert cb.language == "py"
        assert "code" in cb.content

    def test_nested_list(self):
        parser = MarkdownParser()
        transformer = ASTTransformer()
        md = "- a\n  - b"
        tokens = parser.parse(md)
        doc = transformer.transform(tokens)
        assert any(isinstance(b, ListBlock) for b in doc.blocks)


class TestRenderer:
    def test_render_document(self):
        renderer = TelegramRenderer()
        doc = Document(blocks=[
            Heading(level=1, children=[TextNode(content="Title")]),
            Paragraph(children=[TextNode(content="Text")]),
        ])
        html = renderer.render(doc)
        assert "<b>Title</b>" in html
        assert "Text" in html

    def test_render_styles(self):
        renderer = TelegramRenderer()
        doc = Document(blocks=[
            Paragraph(children=[
                TextNode(content="bold", styles=[TextStyle.BOLD]),
                TextNode(content=" "),
                TextNode(content="italic", styles=[TextStyle.ITALIC]),
            ]),
        ])
        html = renderer.render(doc)
        assert "<b>bold</b>" in html
        assert "<i>italic</i>" in html

    def test_render_code_block(self):
        renderer = TelegramRenderer()
        doc = Document(blocks=[
            CodeBlock(content="x = 1", language="python"),
        ])
        html = renderer.render(doc)
        assert '<pre><code class="language-python">' in html

    def test_render_link(self):
        renderer = TelegramRenderer()
        doc = Document(blocks=[
            Paragraph(children=[
                TextNode(content="click", url="https://example.com"),
            ]),
        ])
        html = renderer.render(doc)
        assert '<a href="https://example.com">click</a>' in html


class TestSplitter:
    def test_short_message_single_part(self):
        renderer = TelegramRenderer()
        splitter = MessageSplitter(renderer)
        doc = Document(blocks=[Paragraph(children=[TextNode(content="short")])])
        parts = splitter.split(doc)
        assert len(parts) == 1

    def test_long_message_split(self):
        renderer = TelegramRenderer()
        splitter = MessageSplitter(renderer)
        # Create a document with many blocks that exceed 4096 chars total
        blocks = [
            Paragraph(children=[TextNode(content="x" * 200)])
            for _ in range(30)
        ]
        doc = Document(blocks=blocks)
        parts = splitter.split(doc)
        assert len(parts) > 1
