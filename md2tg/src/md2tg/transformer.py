from typing import List, Optional
from markdown_it.token import Token
from .ast_nodes import (
    Document, BaseBlock, Heading, Paragraph, Quote, CodeBlock,
    ListBlock, ListItem, Table, TableRow, TableCell, TextNode, TextStyle
)

class ASTTransformer:
    def transform(self, tokens: List[Token]) -> Document:
        doc = Document()
        # Stack allows us to track nesting. 
        # But we need a way to know "where to add the next node".
        # We can store (Node, children_list_ref) tuples or just the Node if we standardize .children
        # However, Table/List have specific structures.
        
        # Simpler approach: 
        # A stack of "Container" objects that can accept the current block type.
        # But tokens are flat for blocks.
        
        block_stack: List[BaseBlock] = [] 
        # We'll use a specific root container for the doc
        root_children = doc.blocks
        current_container_list = root_children
        
        # We also need to track parent nodes to climb back up
        # format: (Node, parent_list_to_resume_adding_to)
        
        # Actually markdown-it flow is nice:
        # open -> create node, add to current_container, enter node
        # close -> leave node
        
        # Because my AST is strictly typed (Table has rows, List has items), 
        # I need to be careful about what I push to stack.
        
        # Stack will hold: (Node_Instance, list_of_children_of_that_node)
        
        stack = []
        
        i = 0
        while i < len(tokens):
            token = tokens[i]
            t_type = token.type
            
            # --- BLOCKS ---
            
            if t_type == "heading_open":
                level = int(token.tag.replace("h", ""))
                node = Heading(level=level)
                self._add_node(stack, current_container_list, node)
                # Headings in MD are usually flat content, but in my AST they contain TextNodes
                # We expect an inline token next, then heading_close
                # So we push this to stack to capture the inline content
                stack.append((node, node.children))
                current_container_list = node.children
                
            elif t_type == "heading_close":
                stack.pop()
                current_container_list = stack[-1][1] if stack else root_children

            elif t_type == "paragraph_open":
                # If we are inside a Quote, this paragraph belongs to the Quote
                node = Paragraph()
                self._add_node(stack, current_container_list, node)
                stack.append((node, node.children))
                current_container_list = node.children

            elif t_type == "paragraph_close":
                stack.pop()
                current_container_list = stack[-1][1] if stack else root_children

            elif t_type == "blockquote_open":
                node = Quote()
                self._add_node(stack, current_container_list, node)
                stack.append((node, node.children))
                current_container_list = node.children

            elif t_type == "blockquote_close":
                stack.pop()
                current_container_list = stack[-1][1] if stack else root_children
                
            elif t_type == "bullet_list_open" or t_type == "ordered_list_open":
                ordered = (t_type == "ordered_list_open")
                node = ListBlock(ordered=ordered)
                self._add_node(stack, current_container_list, node)
                stack.append((node, node.items))
                current_container_list = node.items

            elif t_type == "bullet_list_close" or t_type == "ordered_list_close":
                stack.pop()
                current_container_list = stack[-1][1] if stack else root_children
            
            elif t_type == "list_item_open":
                node = ListItem()
                self._add_node(stack, current_container_list, node)
                stack.append((node, node.children))
                current_container_list = node.children

            elif t_type == "list_item_close":
                stack.pop()
                current_container_list = stack[-1][1] if stack else root_children
                
            elif t_type == "fence" or t_type == "code_block":
                # These are self-contained
                lang = token.info if token.info else None
                node = CodeBlock(content=token.content, language=lang)
                self._add_node(stack, current_container_list, node)
                
            # --- TABLES ---
            
            elif t_type == "table_open":
                node = Table()
                self._add_node(stack, current_container_list, node)
                stack.append((node, node.rows))
                current_container_list = node.rows
                
            elif t_type == "table_close":
                stack.pop()
                current_container_list = stack[-1][1] if stack else root_children
                
            elif t_type == "thead_open" or t_type == "tbody_open":
                # We ignore strict thead/tbody structure in our simple AST 
                # and just treat them as passthrough to rows, 
                # BUT we need to not break the stack.
                # Since Table expects TableRow in `node.rows`, and thead children are TRs,
                # we just don't create a node but we DO NOT change the current_container_list
                # because the TRs should go into Table.rows directly? 
                # Actually, markdown-it nesting: table -> thead -> tr.
                # So if I don't change container, TRs go to Table.rows. Correct.
                pass
                
            elif t_type == "thead_close" or t_type == "tbody_close":
                pass
                
            elif t_type == "tr_open":
                node = TableRow()
                self._add_node(stack, current_container_list, node)
                stack.append((node, node.cells))
                current_container_list = node.cells
                
            elif t_type == "tr_close":
                stack.pop()
                current_container_list = stack[-1][1] if stack else root_children
                
            elif t_type == "th_open" or t_type == "td_open":
                is_header = (t_type == "th_open")
                align = token.attrs.get("style", "") # Markdown-it puts alignment in attrs usually or style
                # Actually markdown-it-py often puts 'style': 'text-align:center' in attrs if configured 
                # or we might need to check token.attrs for 'align'.
                # For GFM, it's usually in attrs.
                node = TableCell(header=is_header)
                self._add_node(stack, current_container_list, node)
                stack.append((node, node.children))
                current_container_list = node.children

            elif t_type == "th_close" or t_type == "td_close":
                stack.pop()
                current_container_list = stack[-1][1] if stack else root_children

            # --- INLINE ---
            elif t_type == "inline":
                # Process inline tokens and add TextNodes to current container
                # Current container MUST be a list that accepts TextNode (Paragraph, Heading, TableCell)
                text_nodes = self._process_inline(token.children)
                current_container_list.extend(text_nodes)
            
            i += 1
            
        return doc

    def _add_node(self, stack, current_list, node):
        """Helper to safely add node to current container"""
        current_list.append(node)

    def _process_inline(self, tokens: List[Token]) -> List[TextNode]:
        nodes = []
        active_styles = set()
        active_link = None
        
        if not tokens:
            return []
            
        for token in tokens:
            t_type = token.type
            
            if t_type == "text":
                styles_list = [TextStyle(s) for s in active_styles]
                if active_link:
                    # If inside a link, we mark it.
                    # Note: Our AST defines URL as a style or property? 
                    # Use text style URL? Or property? Node def: url: Optional[str]
                    nodes.append(TextNode(content=token.content, styles=styles_list, url=active_link))
                else:
                    nodes.append(TextNode(content=token.content, styles=styles_list))
                    
            elif t_type == "code_inline":
                # Code is a style but also content
                styles_list = [TextStyle(s) for s in active_styles]
                styles_list.append(TextStyle.CODE)
                nodes.append(TextNode(content=token.content, styles=styles_list, url=active_link))
                
            elif t_type == "strong_open":
                active_styles.add("bold")
            elif t_type == "strong_close":
                active_styles.discard("bold")
                
            elif t_type == "em_open":
                active_styles.add("italic")
            elif t_type == "em_close":
                active_styles.discard("italic")
                
            elif t_type == "s_open":
                active_styles.add("strikethrough")
            elif t_type == "s_close":
                active_styles.discard("strikethrough")
                
            elif t_type == "link_open":
                active_link = token.attrs.get("href", "")
            elif t_type == "link_close":
                active_link = None
            
            # HTML Inline support for Underline / Spoiler
            elif t_type == "html_inline":
                tag = token.content.lower() # e.g. "<u>", "</u>", "<br>", "<br/>"
                
                # Manual simple parsing
                if tag.startswith("</"):
                    # Closing tag
                    if tag.startswith("</u>"):
                        active_styles.discard("underline")
                    elif tag.startswith("</tg-spoiler>") or tag.startswith("</span>"):
                        # We might close spoiler or whatever span. 
                        # Simple check for tg-spoiler stack? 
                        # We only support tg-spoiler now via converter.
                        if "spoiler" in active_styles:
                            active_styles.discard("spoiler")
                    elif tag.startswith("</s>") or tag.startswith("</strike>") or tag.startswith("</del>"):
                        active_styles.discard("strikethrough")
                    elif tag.startswith("</b>") or tag.startswith("</strong>"):
                        active_styles.discard("bold")
                    elif tag.startswith("</i>") or tag.startswith("</em>"):
                        active_styles.discard("italic")
                
                else:
                    # Opening tag
                    if tag.startswith("<u>") or tag.startswith("<ins>"):
                        active_styles.add("underline")
                    elif tag.startswith("<tg-spoiler>") or 'class="tg-spoiler"' in tag:
                        active_styles.add("spoiler")
                    elif tag.startswith("<s>") or tag.startswith("<strike>") or tag.startswith("<del>"):
                        active_styles.add("strikethrough")
                    elif tag.startswith("<b>") or tag.startswith("<strong>"):
                        active_styles.add("bold")
                    elif tag.startswith("<i>") or tag.startswith("<em>"):
                        active_styles.add("italic")
                    elif tag.startswith("<br") or tag == "\n":
                        # Convert <br> to newline node?
                        nodes.append(TextNode(content="\n", styles=[]))
                
            # Linebreaks in inline context (softbreak/hardbreak)
            elif t_type == "softbreak":
                nodes.append(TextNode(content=" ", styles=[])) # or \n depending on preference
            elif t_type == "hardbreak":
                nodes.append(TextNode(content="\n", styles=[]))
                
        # Merge adjacent text nodes with same styles? 
        # Optional optimization.
        return nodes
