import os
import asyncio
from aiogram import Bot, Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

from bot.core.database import get_user_prompt, get_global_prompts
from system_prompts import get_system_prompt

# Load environment variables
load_dotenv()
token = os.getenv("TOKEN")

# --- Bot and Dispatcher Initialization ---
bot = Bot(token=token)
dp = Dispatcher(storage=MemoryStorage())

# --- Global State Variables ---
class contextLock:
    lock = asyncio.Lock()

    async def __aenter__(self):
        await self.lock.acquire()

    async def __aexit__(self, exc_type, exc_value, exc_traceback):
        self.lock.release()

ACTIVE_CHATS = {}
ACTIVE_CHATS_LOCK = contextLock()
modelname = os.getenv("INITMODEL")
mention = None

# --- Utility Functions ---
async def get_bot_info():
    global mention
    if mention is None:
        get = await bot.get_me()
        mention = f"@{get.username}"
    return mention

async def ensure_system_prompt(user_id, messages):
    selected_prompt_id = get_user_prompt(user_id)
    system_prompt_content = ""
    if selected_prompt_id is None:
        system_prompt_content = get_system_prompt("default")["prompt"]
    else:
        prompts = get_global_prompts()
        for p_id, _, text in prompts:
            if p_id == selected_prompt_id:
                system_prompt_content = text
                break
    if system_prompt_content:
        if not messages or messages[0].get("role") != "system":
            messages.insert(0, {"role": "system", "content": system_prompt_content})
        else:
            messages[0]["content"] = system_prompt_content
    return messages