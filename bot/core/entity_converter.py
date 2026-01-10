import sys
from typing import List, Tuple
from aiogram.types import MessageEntity

# Special characters that need escaping in Markdown (GFM)
# We only escape them *inside* the entities we generate, to prevent double parsing.
MD_ESCAPABLE = {
    "*": "\\*",
    "_": "\\_",
    "~": "\\~",
    "`": "\\`",
    "[": "\\[",
    "]": "\\]",
    "(": "\\(",
    ")": "\\)",
    # "!" is for images, usually good to escape but less critical here
    "\\": "\\\\", 
}

def escape_markdown(text: str) -> str:
    """Escape markdown characters in text."""
    return "".join(MD_ESCAPABLE.get(c, c) for c in text)

def _utf16_slice(text: str, offset: int, length: int) -> str:
    """
    Python strings are indexed by unicode code points (mostly).
    Telegram offsets are in UTF-16 code units.
    We need to find the correct start/end indices in the Python string.
    """
    # Optimization: if text contains only BMP characters (len == utf16_len),
    # we can just slice directly.
    # Check if we have wide chars (outside BMP).
    # Python 3.3+ 'str' is flexible representation.
    
    # Slow but correct way: encode to utf-16-le, slice bytes, decode.
    # Note: utf-16 adds BOM usually, we need to handle that.
    
    # Actually, simpler: encode('utf-16-le') produces 2 bytes per code unit.
    # So offset*2, length*2.
    
    try:
        encoded = text.encode('utf-16-le')
        start_byte = offset * 2
        end_byte = (offset + length) * 2
        
        sliced_bytes = encoded[start_byte:end_byte]
        return sliced_bytes.decode('utf-16-le')
    except Exception:
        # Fallback if something goes wrong (shouldn't with valid offsets)
        return text[offset : offset + length]

def _utf16_len(text: str) -> int:
    return len(text.encode('utf-16-le')) // 2

def apply_entities(text: str, entities: List[MessageEntity]) -> str:
    if not entities:
        return text

    # We need to map entities to ranges in the python string.
    # Since recalculating indices for every entity is expensive via encoding,
    # let's try to do it once or map efficiently.
    
    # 1. Convert text to UTF-16 LE bytes
    encoded_text = text.encode('utf-16-le')
    
    # 2. Collect segments
    # Each segment: (start_byte_idx, end_byte_idx, entity)
    # Gaps are filled with "None" entity.
    
    segments = []
    
    # Sort entities just in case
    sorted_entities = sorted(entities, key=lambda e: e.offset)
    
    current_byte_idx = 0
    
    for entity in sorted_entities:
        start_byte = entity.offset * 2
        end_byte = (entity.offset + entity.length) * 2
        
        # Gap before entity
        if start_byte > current_byte_idx:
            gap_bytes = encoded_text[current_byte_idx:start_byte]
            segments.append((gap_bytes.decode('utf-16-le'), None))
            
        # Entity content
        content_bytes = encoded_text[start_byte:end_byte]
        content_str = content_bytes.decode('utf-16-le')
        segments.append((content_str, entity))
        
        current_byte_idx = end_byte
        
    # Gap after last entity
    if current_byte_idx < len(encoded_text):
        gap_bytes = encoded_text[current_byte_idx:]
        segments.append((gap_bytes.decode('utf-16-le'), None))
        
    # 3. Build result string
    result = []
    for content, entity in segments:
        if not entity:
            result.append(content) # Raw text, let parser handle it
            continue
            
        # Escape content inside entity to treat it as "final" text
        cleaned = escape_markdown(content)
        
        # Map entity types to Markdown
        if entity.type == "bold":
            result.append(f"**{cleaned}**")
        elif entity.type == "italic":
            result.append(f"_{cleaned}_")
        elif entity.type == "strikethrough":
            result.append(f"~~{cleaned}~~")
        elif entity.type == "code":
            # Code inside usually doesn't need escaping in the same way,
            # but if it contains backticks, we have an issue.
            # Markdown code spans treat backslash as literal, so we do NOT escape_markdown(content).
            # We only need to ensure we wrap it in enough backticks.
            # Note: If content ends with backtick, we need space padding.
            
            # Simple heuristic for backticks count
            max_tick_seq = 0
            current_seq = 0
            for char in content:
                if char == "`":
                    current_seq += 1
                else:
                    max_tick_seq = max(max_tick_seq, current_seq)
                    current_seq = 0
            max_tick_seq = max(max_tick_seq, current_seq)
            
            ticks = "`" * (max_tick_seq + 1)
            
            # Padding needed if content starts/ends with backtick
            padding = " " if content.startswith("`") or content.endswith("`") else ""
            
            result.append(f"{ticks}{padding}{content}{padding}{ticks}")

        elif entity.type == "pre":
            lang = entity.language or ""
            # Block code: also do not escape. 
            # Needs to be wrapped in ``` or ~~~.
            # If content contains ```, use ~~~.
            fence = "```"
            if "```" in content:
                fence = "~~~"
                if "~~~" in content:
                   # Extremely rare, just duplicate fence length
                   fence = "````"
            
            result.append(f"{fence}{lang}\n{content}\n{fence}")

        elif entity.type == "text_link":
            url = entity.url
            result.append(f"[{cleaned}]({url})")
        elif entity.type == "text_mention":
            user = entity.user
            # tg://user?id=123456
            url = f"tg://user?id={user.id}"
            result.append(f"[{cleaned}]({url})")
        elif entity.type == "underline":
            result.append(f"<u>{cleaned}</u>")
        elif entity.type == "spoiler":
            result.append(f"<tg-spoiler>{cleaned}</tg-spoiler>")
        else:
            # Unsupported or non-visual entity type
            # Return raw content (maybe escaped if mixed?) 
            # If we return unescaped, it might trigger MD.
            # The safest is to return escaped text so it doesn't parse as MD accidentally,
            # preserving the visual text exactly as is.
            result.append(cleaned)
            
    return "".join(result)
