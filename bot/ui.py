from aiogram import types
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder

# --- Keyboards ---

start_kb = InlineKeyboardBuilder()
start_kb.row(
    types.InlineKeyboardButton(text="ℹ️ About", callback_data="about"),
)

settings_kb = InlineKeyboardBuilder()
settings_kb.row(
    types.InlineKeyboardButton(text="🔄 Switch LLM", callback_data="switchllm"),
    types.InlineKeyboardButton(text="🗑️ Delete LLM", callback_data="delete_model"),
)
settings_kb.row(
    types.InlineKeyboardButton(text="⚙️ Manage Prompts", callback_data="admin_prompts"),
)
settings_kb.row(
    types.InlineKeyboardButton(text="📋 Remove Users", callback_data="list_users"),
)
settings_kb.row(
    types.InlineKeyboardButton(text="❌ Close", callback_data="close_settings"),
)

# --- FSM States ---


class ChatCreationStates(StatesGroup):
    awaiting_name = State()


class PromptStates(StatesGroup):
    awaiting_name = State()
    awaiting_text = State()
