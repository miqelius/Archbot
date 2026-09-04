"""
bot/handlers/ - Aiogram 3 message and callback handlers
Handles user text input, document uploads, and status polling
"""

from aiogram import Router, types, F
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from typing import Optional
import logging
import uuid
import httpx
from datetime import datetime

from core.core_config import settings
from schemas.schemas_translation import (
    TranslationJobRequest,
    SourceType,
    JobStatus,
)

logger = logging.getLogger(__name__)

# Router for grouping related handlers
router = Router(name="translation_handlers")


# ============================================================================
# FSM (Finite State Machine) for user conversation flow
# ============================================================================

class TranslationStates(StatesGroup):
    """States for translation conversation flow"""
    
    waiting_for_input = State()  # Waiting for text or document
    processing = State()  # Job is being processed
    result_ready = State()  # Result available


# ============================================================================
# START & HELP COMMANDS
# ============================================================================

@router.message(Command("start"))
async def cmd_start(message: types.Message, state: FSMContext) -> None:
    """Handle /start command"""
    
    welcome_text = f"""
👋 *Welcome to Historical Translator Bot!*

I can help you translate text into formal, historical-diplomatic style.

*How to use:*
1️⃣ Send me text to translate
2️⃣ Or upload a document (PDF, DOCX, image)
3️⃣ I'll translate and stylize it automatically

*Commands:*
/start - Show this message
/help - Get detailed instructions
/status <job_id> - Check translation status
/settings - Configure language pair

*Example:*
Just type or paste text and I'll handle the rest!
"""
    
    await message.answer(welcome_text, parse_mode="Markdown")
    await state.set_state(TranslationStates.waiting_for_input)


@router.message(Command("help"))
async def cmd_help(message: types.Message) -> None:
    """Detailed help message"""
    
    help_text = """
📖 *Detailed Instructions*

*Sending Text:*
Simply type or paste any text you want translated. 
The translation will maintain formal, diplomatic tone.

*Uploading Documents:*
You can send:
- 📄 PDF files
- 📝 Word documents (.docx)
- 🖼 Images (with OCR)

Maximum file size: 50MB

*Translation Process:*
1. 🔤 *Translator* - Converts text accurately
2. 🎭 *Stylist* - Applies historical-diplomatic tone
3. ✅ *Quality Control* - Reviews and corrects

*Understanding Results:*
- *Final Translation* - The complete, polished translation
- *Quality Score* - 0-100 rating of how good it is
- *Issues* - Any problems found (if score < 75)

*Tips:*
- Provide context for better results
- Longer texts usually get better stylization
- Check the quality report for detailed feedback

Need help? Contact @gio_dev
"""
    
    await message.answer(help_text, parse_mode="Markdown")


# ============================================================================
# TEXT TRANSLATION
# ============================================================================

@router.message(
    StateFilter(TranslationStates.waiting_for_input),
    F.text,
    ~F.text.startswith("/"),
)
async def handle_text_input(
    message: types.Message,
    state: FSMContext,
) -> None:
    """
    Handle user text input for translation.
    
    Flow:
    1. Validate text length
    2. Create job via API
    3. Update user status
    4. Start polling for result
    """
    
    user_text = message.text.strip()
    
    # Validate
    if len(user_text) < 10:
        await message.answer(
            "❌ Text too short. Please provide at least 10 characters."
        )
        return
    
    if len(user_text) > 5000:
        await message.answer(
            "⚠️ Text too long. Maximum 5000 characters. "
            "Use /upload for larger texts."
        )
        return
    
    # Show typing indicator
    await message.bot.send_chat_action(
        chat_id=message.chat.id,
        action="typing"
    )
    
    try:
        # Create job via FastAPI
        job_id = await create_translation_job(
            user_id=str(message.from_user.id),
            username=message.from_user.username,
            source_type=SourceType.text,
            text=user_text,
        )
        
        # Store job_id in state for later reference
        await state.update_data(current_job_id=job_id)
        await state.set_state(TranslationStates.processing)
        
        # Send confirmation
        confirmation = (
            f"✅ Translation started!\n\n"
            f"*Job ID:* `{job_id}`\n\n"
            f"Processing your text ({len(user_text)} chars)...\n"
            f"This usually takes 30-60 seconds."
        )
        
        msg = await message.answer(
            confirmation,
            parse_mode="Markdown",
            reply_markup=get_status_keyboard(job_id)
        )
        
        # Start polling for result
        await poll_job_status(
            message=message,
            job_id=job_id,
            state=state,
            max_attempts=60,  # Poll for up to 10 minutes
        )
    
    except Exception as e:
        logger.error(f"Text translation failed: {e}")
        await message.answer(
            f"❌ Error starting translation: {str(e)}\n\n"
            "Please try again or contact support."
        )


# ============================================================================
# DOCUMENT UPLOAD
# ============================================================================

@router.message(F.document)
async def handle_document_upload(
    message: types.Message,
    state: FSMContext,
) -> None:
    """Handle document uploads (PDF, DOCX, images)"""
    
    document = message.document
    
    # Validate file size
    max_size_bytes = 20 * 1024 * 1024
    if document.file_size > max_size_bytes:
        await message.answer(
            f"❌ File too large. Maximum {20}MB."
        )
        return
    
    # Validate file type
    allowed_extensions = {".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png"}
    file_extension = f".{document.file_name.split('.')[-1].lower()}"
    
    if file_extension not in allowed_extensions:
        await message.answer(
            f"❌ Unsupported file type. Allowed: PDF, DOCX, JPG, PNG"
        )
        return
    
    # Show uploading status
    progress_msg = await message.answer(
        "📤 Uploading and extracting text...\n"
        "This may take a minute for large files."
    )
    
    try:
        # Download file from Telegram
        file = await message.bot.get_file(document.file_id)
        file_bytes = await message.bot.session.download_file(file)
        
        # Create job via API
        job_id = await create_translation_job(
            user_id=str(message.from_user.id),
            username=message.from_user.username,
            source_type=SourceType.document,
            file_bytes=file_bytes,
            file_name=document.file_name,
        )
        
        await state.update_data(current_job_id=job_id)
        await state.set_state(TranslationStates.processing)
        
        # Update status
        await progress_msg.edit_text(
            f"✅ Document received!\n\n"
            f"*Job ID:* `{job_id}`\n\n"
            f"Extracting text and translating...\n"
            f"Large documents may take several minutes.",
            parse_mode="Markdown",
            reply_markup=get_status_keyboard(job_id)
        )
        
        # Poll for result
        await poll_job_status(
            message=message,
            job_id=job_id,
            state=state,
            max_attempts=120,  # Up to 20 minutes for large docs
        )
    
    except Exception as e:
        logger.error(f"Document upload failed: {e}")
        await progress_msg.edit_text(
            f"❌ Upload failed: {str(e)}\n\n"
            "Please try again."
        )


# ============================================================================
# STATUS POLLING & RESULT DISPLAY
# ============================================================================

async def poll_job_status(
    message: types.Message,
    job_id: str,
    state: FSMContext,
    max_attempts: int = 60,
    poll_interval: int = 3,  # seconds between polls
) -> None:
    """
    Poll job status until completion or timeout.
    Updates user with progress.
    """
    import asyncio
    
    status_msg = None
    
    for attempt in range(max_attempts):
        try:
            # Check job status
            job_status = await get_job_status(job_id)
            
            if not job_status:
                logger.warning(f"Job {job_id} not found")
                continue
            
            status = job_status.get("status")
            progress = job_status.get("progress_percent", 0)
            
            # Update or create status message
            status_text = format_job_status(
                job_id=job_id,
                status=status,
                progress=progress,
            )
            
            if status_msg is None:
                status_msg = await message.answer(
                    status_text,
                    parse_mode="Markdown",
                )
            else:
                await status_msg.edit_text(
                    status_text,
                    parse_mode="Markdown",
                )
            
            # Check if complete
            if status == JobStatus.completed:
                await display_result(
                    message=message,
                    job_id=job_id,
                    state=state,
                )
                return
            
            elif status == JobStatus.failed:
                await message.answer(
                    f"❌ Translation failed!\n\n"
                    f"*Job ID:* `{job_id}`\n"
                    f"Error: {job_status.get('error_message', 'Unknown error')}"
                )
                return
            
            # Wait before next poll
            await asyncio.sleep(poll_interval)
        
        except Exception as e:
            logger.error(f"Status poll error: {e}")
            await asyncio.sleep(poll_interval)
    
    # Timeout
    if status_msg:
        await status_msg.edit_text(
            f"⏱️ Translation is taking longer than expected.\n\n"
            f"*Job ID:* `{job_id}`\n\n"
            f"You can check status later with: `/status {job_id}`",
            parse_mode="Markdown",
        )


async def display_result(
    message: types.Message,
    job_id: str,
    state: FSMContext,
) -> None:
    """Display completed translation result"""
    
    try:
        result = await get_job_result(job_id)
        
        if not result:
            await message.answer("❌ Could not retrieve result")
            return
        
        # Build result message
        result_text = f"""
✅ *Translation Complete!*

*Job ID:* `{job_id}`

*Original Text:*
```
{result.get('original_text', '')[:200]}...
```

*Final Translation:*
```
{result.get('final_translation', '')}
```

*Quality Score:* {result.get('quality_score', 0)}/100

"""
        
        # Add quality issues if any
        quality_report = result.get("quality_report")
        if quality_report and quality_report.get("issues"):
            result_text += "*Issues Found:*\n"
            for issue in quality_report["issues"][:3]:  # Show first 3 issues
                result_text += (
                    f"• {issue.get('issue_type')}: "
                    f"{issue.get('description')}\n"
                )
            if len(quality_report["issues"]) > 3:
                result_text += f"• ... and {len(quality_report['issues']) - 3} more\n"
        
        result_text += "\n*Would you like to:*"
        
        await message.answer(
            result_text,
            parse_mode="Markdown",
            reply_markup=get_result_keyboard(job_id),
        )
        
        # Reset state
        await state.set_state(TranslationStates.waiting_for_input)
    
    except Exception as e:
        logger.error(f"Result display failed: {e}")
        await message.answer(
            f"❌ Error displaying result: {str(e)}"
        )


# ============================================================================
# STATUS COMMAND
# ============================================================================

@router.message(Command("status"))
async def cmd_status(message: types.Message) -> None:
    """Handle /status <job_id> command"""
    
    parts = message.text.split()
    if len(parts) < 2:
        await message.answer(
            "Usage: `/status <job_id>`\n\n"
            "Example: `/status 550e8400-e29b-41d4-a716-446655440000`",
            parse_mode="Markdown",
        )
        return
    
    job_id = parts[1]
    
    try:
        job_status = await get_job_status(job_id)
        
        if not job_status:
            await message.answer(
                f"❌ Job `{job_id}` not found",
                parse_mode="Markdown",
            )
            return
        
        status_text = format_job_status(
            job_id=job_id,
            status=job_status.get("status"),
            progress=job_status.get("progress_percent", 0),
        )
        
        await message.answer(
            status_text,
            parse_mode="Markdown",
            reply_markup=get_status_keyboard(job_id),
        )
    
    except Exception as e:
        logger.error(f"Status check failed: {e}")
        await message.answer(
            f"❌ Error: {str(e)}"
        )


# ============================================================================
# API HELPERS
# ============================================================================

async def create_translation_job(
    user_id: str,
    username: Optional[str],
    source_type: SourceType,
    text: Optional[str] = None,
    file_bytes: Optional[bytes] = None,
    file_name: Optional[str] = None,
) -> str:
    """Create translation job via FastAPI endpoint"""
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        url = f"{settings.api_host}:{settings.api_port}{settings.api_prefix}/jobs"
        
        payload = {
            "telegram_user_id": user_id,
            "telegram_username": username,
            "source_type": source_type.value,
            "source_language": "ka",
            "target_language": "en",
        }
        
        if text:
            payload["text"] = text
        
        response = await client.post(url, json=payload)
        response.raise_for_status()
        
        result = response.json()
        return result["job_id"]


async def get_job_status(job_id: str) -> Optional[dict]:
    """Get job status from API"""
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        url = (
            f"{settings.api_host}:{settings.api_port}"
            f"{settings.api_prefix}/jobs/{job_id}/status"
        )
        
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Status API error: {e}")
            return None


async def get_job_result(job_id: str) -> Optional[dict]:
    """Get complete job result from API"""
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        url = (
            f"{settings.api_host}:{settings.api_port}"
            f"{settings.api_prefix}/jobs/{job_id}/result"
        )
        
        try:
            response = await client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Result API error: {e}")
            return None


# ============================================================================
# KEYBOARD & FORMATTING HELPERS
# ============================================================================

def get_status_keyboard(job_id: str) -> types.InlineKeyboardMarkup:
    """Status check inline keyboard"""
    
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="🔄 Refresh Status",
                    callback_data=f"status:{job_id}"
                ),
                types.InlineKeyboardButton(
                    text="❌ Cancel",
                    callback_data=f"cancel:{job_id}"
                ),
            ]
        ]
    )


def get_result_keyboard(job_id: str) -> types.InlineKeyboardMarkup:
    """Result action keyboard"""
    
    return types.InlineKeyboardMarkup(
        inline_keyboard=[
            [
                types.InlineKeyboardButton(
                    text="📋 Copy Translation",
                    callback_data=f"copy:{job_id}"
                ),
                types.InlineKeyboardButton(
                    text="📥 Download Report",
                    callback_data=f"download:{job_id}"
                ),
            ],
            [
                types.InlineKeyboardButton(
                    text="🆕 New Translation",
                    callback_data="new"
                ),
            ]
        ]
    )


def format_job_status(
    job_id: str,
    status: str,
    progress: int = 0,
) -> str:
    """Format job status for display"""
    
    status_emoji = {
        JobStatus.pending: "⏳",
        JobStatus.processing: "⚙️",
        JobStatus.translating: "🔄",
        JobStatus.reviewing: "🔍",
        JobStatus.completed: "✅",
        JobStatus.failed: "❌",
    }.get(status, "❓")
    
    progress_bar = "▰" * (progress // 10) + "▱" * (10 - progress // 10)
    
    return (
        f"{status_emoji} *Status: {status.upper()}*\n\n"
        f"Progress: `{progress_bar}` {progress}%\n"
        f"Job ID: `{job_id}`"
    )
