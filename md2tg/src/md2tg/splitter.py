from typing import List
from .ast_nodes import Document
from .renderer import TelegramRenderer

class MessageSplitter:
    def __init__(self, renderer: TelegramRenderer):
        self.renderer = renderer
        self.limit = 4096

    def split(self, doc: Document) -> List[str]:
        messages = []
        current_chunk = ""
        
        for block in doc.blocks:
            # Render individual block
            rendered_block = self.renderer.render_block(block)
            if not rendered_block: 
                continue
            
            # Calculate hypothetical length: current + separator + new
            current_len = len(current_chunk)
            block_len = len(rendered_block)
            separator_len = 2 if current_len > 0 else 0 # "\n\n"
            
            total_len = current_len + separator_len + block_len
            
            if total_len > self.limit:
                # If the chunk is full, push it
                if current_chunk:
                    messages.append(current_chunk)
                    current_chunk = rendered_block
                else:
                    # If we are here, current_chunk is empty, but the single block is > 4096
                    # Use case: Giant code block or table.
                    # We can't split it without violating "don't cut HTML string".
                    # We push it as its own message (it will likely fail on Telegram API side, 
                    # but we followed the internal architecture rules).
                    messages.append(rendered_block)
                    current_chunk = ""
            else:
                if current_chunk:
                    current_chunk += "\n\n" + rendered_block
                else:
                    current_chunk = rendered_block
                    
        if current_chunk:
            messages.append(current_chunk)
            
        return messages
