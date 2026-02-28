# md2tg

**Convert Markdown to Telegram-compatible HTML.**

A lightweight Python library that parses Markdown into an internal AST and renders
it as HTML understood by the Telegram Bot API (`HTML` parse mode).

## Features

- Headings, paragraphs, blockquotes
- Bold, italic, underline, strikethrough, spoiler
- Inline code and fenced code blocks (with language annotation)
- Ordered and unordered (nested) lists
- Tables (rendered as monospace `<pre>` blocks)
- Links
- Automatic message splitting to fit the Telegram 4 096-character limit

## Installation

```bash
pip install md2tg
```

Or, with [uv](https://docs.astral.sh/uv/):

```bash
uv add md2tg
```

## Quick start

```python
from md2tg import convert

# Returns a list of HTML strings, each ≤ 4096 characters
parts = convert("**Hello** _world_")
print(parts)
# ['<b>Hello</b> <i>world</i>']
```

### Lower-level API

```python
from md2tg import MarkdownParser, ASTTransformer, TelegramRenderer, MessageSplitter

parser = MarkdownParser()
transformer = ASTTransformer()
renderer = TelegramRenderer()
splitter = MessageSplitter(renderer)

tokens = parser.parse("# Title\nParagraph text")
doc = transformer.transform(tokens)

html = renderer.render(doc)        # single HTML string
parts = splitter.split(doc)        # list of strings ≤ 4096 chars
```

## License

MIT
