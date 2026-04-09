import os
import logging
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from bot.core.database import get_user_prompt, get_global_prompts, get_bot_config
from bot.utils.spinner import SpinnerManager

# Load environment variables
load_dotenv()
token = os.getenv("TOKEN")

# --- Bot and Dispatcher Initialization ---
bot = Bot(token=token)
dp = Dispatcher(storage=MemoryStorage())

# --- Global State Variables ---
ACTIVE_CHATS = {}

# Model will be loaded after init_db() via set_modelname_from_db()
modelname = os.getenv("INITMODEL")  # Default from .env initially

mention = None

# Spinner manager for handling animated indicators
spinner_manager: SpinnerManager | None = None


# --- Function to load model from DB after initialization ---
def set_modelname_from_db() -> None:
    """Load the saved model from bot_config after DB is initialized."""
    global modelname
    _saved_model = get_bot_config("current_model")
    if _saved_model:
        modelname = _saved_model


# --- Utility Functions ---
async def get_bot_info() -> str:
    """
    Get bot's username mention (e.g., @MyBot).

    Caches the result globally after first fetch.

    Returns:
        str: Bot's username with @ prefix
    """
    global mention
    if mention is None:
        get = await bot.get_me()
        mention = f"@{get.username}"
    return mention


def cleanup_inactive_chats(timeout_hours: float = 12) -> None:
    """
    Removes inactive entries from ACTIVE_CHATS based on last_activity timestamp.

    Args:
        timeout_hours: Hours of inactivity before removal (default: 12)
    """
    import time

    cutoff_time = time.time() - (timeout_hours * 3600)
    inactive_users = [
        user_id
        for user_id, data in ACTIVE_CHATS.items()
        if data.get("last_activity", 0) < cutoff_time
    ]
    for user_id in inactive_users:
        del ACTIVE_CHATS[user_id]
        logging.info(f"Cleaned up inactive chat for user {user_id}")


async def ensure_system_prompt(user_id: int, messages: list[dict]) -> list[dict]:
    """
    Ensures the correct system prompt is at the beginning of the messages list.
    The prompt can be:
    - None (default)
    - A predefined prompt key string ("default", "code", etc.)
    - A custom prompt ID (stored as string in DB)
    """
    from system_prompts import SYSTEM_PROMPTS

    selected_prompt_id = get_user_prompt(user_id)
    system_prompt_content = ""

    if selected_prompt_id is None:
        # No selection, use default
        system_prompt_content = SYSTEM_PROMPTS["default"]["prompt"]
    elif selected_prompt_id in SYSTEM_PROMPTS:
        # It's a predefined prompt key
        system_prompt_content = SYSTEM_PROMPTS[selected_prompt_id]["prompt"]
    else:
        # It might be a custom prompt ID (stored as string)
        try:
            custom_id = int(selected_prompt_id)
            prompts = get_global_prompts()
            for p_id, _, text in prompts:
                if p_id == custom_id:
                    system_prompt_content = text
                    break
        except (ValueError, TypeError):
            # Invalid format, fallback to default
            logging.warning(f"Invalid prompt_id format for user {user_id}: {selected_prompt_id}")
            system_prompt_content = SYSTEM_PROMPTS["default"]["prompt"]

    if system_prompt_content:
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": system_prompt_content})
        else:
            messages[0]["content"] = system_prompt_content
    return messages
