import html
from typing import List
from .ast_nodes import (
    Document, BaseBlock, Heading, Paragraph, Quote, CodeBlock,
    ListBlock, ListItem, Table, TableRow, TableCell, TextNode, TextStyle
)

class TelegramRenderer:
    def render(self, doc: Document) -> str:
        output = []
        for block in doc.blocks:
            output.append(self.render_block(block))
        return "\n\n".join(filter(None, output)).strip()

    def render_block(self, block: BaseBlock, list_level: int = 0) -> str:
        if isinstance(block, Heading):
            # Telegram doesn't support h1-h6. We use Bold.
            # Maybe add some visual distinction like underlining or # prefix
            text = self._render_children(block.children)
            return f"<b>{text}</b>"
            
        elif isinstance(block, Paragraph):
            return self._render_children(block.children)
            
        elif isinstance(block, Quote):
            # Telegram supports <blockquote>
            content = []
            for child in block.children:
                # We reset list level inside quotes as they are a container
                content.append(self.render_block(child, list_level=0))
            inner = "\n".join(content)
            return f"<blockquote>{inner}</blockquote>"
            
        elif isinstance(block, CodeBlock):
            # <pre><code class="language-python">...</code></pre>
            escaped_content = html.escape(block.content)
            lang_attr = f' class="language-{block.language}"' if block.language else ""
            return f'<pre><code{lang_attr}>{escaped_content}</code></pre>'
            
        elif isinstance(block, ListBlock):
            return self._render_list(block, list_level)
            
        elif isinstance(block, Table):
            return self._render_table(block)
            
        return ""

    def _render_list(self, block: ListBlock, level: int) -> str:
        items = []
        # Use Non-Breaking Space (U+00A0) for indentation because Telegram strips normal spaces
        indent = "\u00A0\u00A0\u00A0" * level 
        
        for index, item in enumerate(block.items):
            prefix = f"{index + 1}. " if block.ordered else "• "
            
            # Combine indent and prefix
            full_prefix = f"{indent}{prefix}"
            
            # ListItem contains blocks (Paragraphs mostly)
            # We pass level + 1 to children if they are nested lists
            item_content = self._render_list_item_children(item.children, level)
            items.append(f"{full_prefix}{item_content}")
            
        return "\n".join(items)

    def _render_list_item_children(self, children: List[BaseBlock], current_level: int) -> str:
        # List items might contain multiple paragraphs. 
        # For a simple list, we join them.
        parts = []
        first = True
        for child in children:
            if isinstance(child, Paragraph):
                # If first paragraph, we just append content.
                # If subsequent paragraphs in same item (rare in simple MD but possible), 
                # we technically should indent them too to align with bullet.
                # For simplicity, we just print them.
                content = self._render_children(child.children)
                if not first:
                    # Align subsequent paragraphs with the text start (indent + bullet len)
                    # This is hard without exact length. simpler to just newline
                    parts.append("\n" + content)
                else:
                    parts.append(content)
                first = False
                
            # Nested lists or other blocks could be recursive here
            elif isinstance(child, ListBlock):
                # Nested list
                # Increase level for nested list
                 parts.append("\n" + self.render_block(child, list_level=current_level + 1))
                 
            else:
                 # Other blocks inside list items (e.g. CodeBlock)
                 # Should we support them?
                 parts.append("\n" + self.render_block(child, list_level=current_level))
                 
        return "".join(parts)

    def _render_children(self, text_nodes: List[TextNode]) -> str:
        return "".join(self._render_text_node(node) for node in text_nodes)

    def _render_text_node(self, node: TextNode) -> str:
        text = html.escape(node.content)
        
        # Apply styles
        # Order matters for strict XML parsers, but nested tags <b`><i>...</i></b> are fine
        
        if TextStyle.CODE in node.styles:
            text = f"<code>{text}</code>"
        
        if TextStyle.BOLD in node.styles:
            text = f"<b>{text}</b>"
            
        if TextStyle.ITALIC in node.styles:
            text = f"<i>{text}</i>"
            
        if TextStyle.STRIKETHROUGH in node.styles:
            text = f"<s>{text}</s>"

        if TextStyle.UNDERLINE in node.styles:
            text = f"<u>{text}</u>"

        if TextStyle.SPOILER in node.styles:
            text = f'<span class="tg-spoiler">{text}</span>'
            
        if node.url:
            text = f'<a href="{node.url}">{text}</a>'
            
        return text

    def _render_table(self, table: Table) -> str:
        # Fallback render: Calculate column widths and use <pre>
        if not table.rows:
            return ""
            
        # 1. Flatten table content to strings to calculate lengths
        # We need to render the content of cells first (without HTML tags if we want strict alignment, 
        # BUT inside <pre> we don't render HTML usually? 
        # Telegram <pre> supports entities. So we CAN have bold inside <pre>.
        # We need plain length for alignment, but rendered string for output.
        
        rendered_grid = []
        plain_grid = []
        
        for row in table.rows:
            r_rendered = []
            r_plain = []
            for cell in row.cells:
                # Render content
                cell_html = self._render_children(cell.children)
                if cell.header:
                    cell_html = f"<b>{cell_html}</b>"
                
                # For length calculation we need the "visible" length. 
                # This is hard because HTML tags are invisible.
                # A simple approximation: strip tags for length calc? 
                # Or just use the content length of text nodes.
                plain_text = "".join(n.content for n in cell.children)
                
                r_rendered.append(cell_html)
                r_plain.append(plain_text)
            
            rendered_grid.append(r_rendered)
            plain_grid.append(r_plain)
            
        if not plain_grid:
            return ""

        cols = len(plain_grid[0])
        col_widths = [0] * cols
        
        for row in plain_grid:
            for i, cell_text in enumerate(row):
                if i < cols:
                    col_widths[i] = max(col_widths[i], len(cell_text))
                    
        # Render rows
        lines = []
        for r_idx, row in enumerate(rendered_grid):
            line_parts = []
            for c_idx, cell_html in enumerate(row):
                if c_idx >= cols: break
                
                # We align based on plain text length
                padding = col_widths[c_idx] - len(plain_grid[r_idx][c_idx])
                line_parts.append(cell_html + " " * padding)
                
            lines.append(" | ".join(line_parts))
            
            # Add separator after header usually? 
            # If the first row was header (how to detect? AST has header flag)
            # My AST TableCell has header=True.
            # Only add separator if the first row actually contains header cells
            has_header = any(cell.header for cell in table.rows[r_idx].cells)
            if has_header and r_idx == 0:
                sep = "-+-".join("-" * w for w in col_widths)
                lines.append(sep)
                
        return f"<pre>{chr(10).join(lines)}</pre>"
