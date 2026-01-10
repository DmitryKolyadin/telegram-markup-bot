import asyncio
import os
import logging
import hashlib
import re
import ssl
import certifi
import aiohttp
from io import BytesIO

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineQueryResultArticle, InputTextMessageContent
from aiogram.utils.markdown import html_decoration
from aiogram import Router

from core.parser import MarkdownParser
from core.transformer import ASTTransformer
from core.renderer import TelegramRenderer
from core.splitter import MessageSplitter
from core.entity_converter import apply_entities

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize dependencies
parser = MarkdownParser()
transformer = ASTTransformer()
renderer = TelegramRenderer()
splitter = MessageSplitter(renderer)

router = Router()

async def fetch_external_content(url: str) -> str | None:
    """Detects GitHub or Pastebin URLs and fetches raw content."""
    # Gist: https://gist.github.com/user/id -> https://gist.github.com/user/id/raw/
    gist_pattern = r"^https?://gist\.github\.com/([^/]+)/([^/]+)/?$"
    # Repo file: https://github.com/user/repo/blob/branch/path -> https://raw.githubusercontent.com/user/repo/branch/path
    repo_pattern = r"^https?://github\.com/([^/]+)/([^/]+)/blob/([^/]+)/(.+)$"
    # Telegraph: https://telegra.ph/Page-Name-12-31
    telegraph_pattern = r"^https?://telegra\.ph/(.+)$"
    
    raw_url = None
    use_telegraph = False
    
    gist_match = re.match(gist_pattern, url)
    if gist_match:
        user, gist_id = gist_match.groups()
        raw_url = f"https://gist.github.com/{user}/{gist_id}/raw/"
        
    repo_match = re.match(repo_pattern, url)
    if repo_match:
        user, repo, branch, path = repo_match.groups()
        raw_url = f"https://raw.githubusercontent.com/{user}/{repo}/{branch}/{path}"

    telegraph_match = re.match(telegraph_pattern, url)
    if telegraph_match:
        # Telegraph needs special handling - we'll fetch the page via API
        use_telegraph = True
        raw_url = url
            
    if not raw_url:
        return None
        
    # Clean raw_url from any accidental whitespace or control chars
    raw_url = raw_url.strip()
    
    # Special handling for Telegraph - fetch content via API
    if use_telegraph:
        path = telegraph_match.group(1)
        api_url = f"https://api.telegra.ph/getPage/{path}?return_content=true"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api_url, timeout=10) as response:
                    if response.status == 200:
                        data = await response.json()
                        if data.get('ok') and 'result' in data and 'content' in data['result']:
                            # Extract text from Telegraph content array
                            content = data['result']['content']
                            text_parts = []
                            for node in content:
                                if isinstance(node, dict) and 'children' in node:
                                    for child in node['children']:
                                        if isinstance(child, str):
                                            text_parts.append(child)
                            return '\n'.join(text_parts) if text_parts else None
        except Exception as e:
            logger.error(f"Failed to fetch Telegraph content: {repr(e)}")
            return None
    
    # Build SSL context
    ssl_ctx = ssl.create_default_context(cafile=certifi.where())
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept": "text/plain, text/markdown, */*",
        "Connection": "close"
    }
    
    async def _do_fetch(verify_ssl: bool):
        # Disable IPv6 if it's causing timeouts in some environments
        connector = aiohttp.TCPConnector(family=0 if verify_ssl else 0, ssl=ssl_ctx if verify_ssl else False)
        async with aiohttp.ClientSession(headers=headers, connector=connector) as session:
            async with session.get(raw_url, timeout=10, allow_redirects=True) as response:
                if response.status == 200:
                    text = await response.text()
                    if text.strip().lower().startswith(("<!doctype", "<html")):
                        logger.warning(f"Fetched content for {raw_url} seems to be HTML, ignoring.")
                        return None
                    return text
                else:
                    logger.error(f"Status {response.status} when fetching {raw_url}")
                return None

    try:
        return await _do_fetch(verify_ssl=True)
    except Exception as e:
        logger.warning(f"Fetch failed for {raw_url} (verify_ssl=True): {repr(e)}. Retrying without SSL/IPv6 tweaks...")
        try:
            # Fallback to simplest possible fetch
            async with aiohttp.ClientSession(headers=headers) as session:
                async with session.get(raw_url, ssl=False, timeout=10) as response:
                    if response.status == 200:
                        return await response.text()
                    return None
        except Exception as e2:
            logger.error(f"Ultimate fetch failure for {raw_url}: {repr(e2)}")

    return None

def process_markdown(text: str) -> list[str]:
    """Pipeline: Parser -> Transformer -> Splitter(Renderer)"""
    tokens = parser.parse(text)
    doc = transformer.transform(tokens)
    return splitter.split(doc)

async def main():
    # Helper for local running
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 <b>Markdown Bot</b>\n\n"
        "Send me any text with <b>Markdown</b> or upload a <code>.md</code> file.\n"
        "I will render it to Telegram HTML messages.",
        parse_mode="HTML"
    )

@router.message(F.text)
async def handle_text(message: types.Message):
    if not message.text:
        return
        
    try:
        # Pre-process native Telegram entities into Markdown for parser
        text_content = apply_entities(message.text, message.entities)
        
        parts = process_markdown(text_content)
        if not parts:
            await message.answer("⚠️ Result was empty.")
            return
            
        for part in parts:
            # We don't disable web_page_preview just in case links are important
            # But usually for docs it's annoying. User didn't specify.
            await message.answer(part, parse_mode="HTML")
            
    except Exception as e:
        logger.exception("Error processing text")
        await message.answer(f"❌ Processing error: {html_decoration.quote(str(e))}")

@router.message(F.document)
async def handle_document(message: types.Message, bot: Bot):
    doc = message.document
    # Check extension
    if not doc.file_name or not (doc.file_name.endswith('.md') or doc.file_name.endswith('.txt')):
        # Silently ignore or useful hint?
        # User said "Документ (.md, .txt)", implying implied filter.
        return

    # Limit file size (e.g., 2MB) to prevent serverless timeout
    if doc.file_size > 2 * 1024 * 1024:
        await message.answer("❌ File too large (max 2MB).")
        return

    try:
        processing_msg = await message.answer("⏳ Downloading and processing...")
        
        # Download
        file_io = BytesIO()
        await bot.download(doc, destination=file_io)
        content = file_io.getvalue().decode('utf-8')
        
        parts = process_markdown(content)
        
        await processing_msg.delete()
        
        for part in parts:
            await message.answer(part, parse_mode="HTML")
            
    except UnicodeDecodeError:
        await message.answer("❌ File encoding must be UTF-8.")
    except Exception as e:
        logger.exception("Error processing file")
        await message.answer(f"❌ Processing error: {html_decoration.quote(str(e))}")

@router.inline_query()
async def handle_inline(inline_query: types.InlineQuery):
    text = inline_query.query.strip()
    if not text:
        # Show button to open Web App for easy input
        # Assuming GitHub Pages deployment at https://<user>.github.io/<repo>/
        # Replace with your actual deployed URL if different
        webapp_url = "https://dmitrykolyadin.github.io/telegram-markup-bot/"
        
        button = types.InlineQueryResultsButton(
            text="Open Editor",
            web_app=types.WebAppInfo(url=webapp_url)
        )
        
        await inline_query.answer(
            results=[],
            button=button,
            cache_time=0,
            is_personal=True
        )
        return

    # Check if text is a GitHub/Pastebin URL
    fetched_content = await fetch_external_content(text)
    
    # If fetched, prioritize it. Otherwise use text as is.
    content_to_parse = fetched_content if fetched_content else text
    
    # Note: inline queries don't pass entities.
    try:
        parts = process_markdown(content_to_parse)
        if not parts:
            return
            
        # Inline mode only supports returning defined results. 
        # We can't really send multiple messages for one inline result.
        # So we just take the first part.
        content = parts[0] 
        # Add warning if truncated?
        if len(parts) > 1:
            content += "\n\n<i>(Content truncated...)</i>"

        result_id = hashlib.md5(text.encode()).hexdigest()
        
        # Determine title/desc based on source
        title = "Render GitHub MD" if fetched_content else "Render Markdown"
        description = text if not fetched_content else "Fetched content from GitHub"
        
        item = InlineQueryResultArticle(
            id=result_id,
            title=title,
            description=description,
            input_message_content=InputTextMessageContent(
                message_text=content,
                parse_mode="HTML",
                # Disable web page preview because we just rendered the link content
                disable_web_page_preview=True
            )
        )
        
        await inline_query.answer([item], cache_time=0, is_personal=True)
        
    except Exception as e:
        logger.error(f"Inline error: {e}")
        pass

token = os.getenv("BOT_TOKEN")
if not token:
    logger.error("BOT_TOKEN is not set")
    exit(1)
        
bot = Bot(token=token)
dp = Dispatcher()

# Register handlers
dp.include_router(router)

if __name__ == "__main__":
    asyncio.run(main())
