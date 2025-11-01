import logging
from aiogram import types, Router
from aiogram.filters.command import Command
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.auth import perms_allowed, perms_admins
from bot.core.database import (
    get_user_chat_sessions,
    create_chat_session,
    load_chat_history,
    delete_chat_session,
)
from bot.ui import ChatCreationStates
from bot.state import ACTIVE_CHATS, ACTIVE_CHATS_LOCK, modelname, ensure_system_prompt

chat_router = Router()


@chat_router.message(Command("reset"))
@perms_allowed
async def command_reset_handler(message: types.Message) -> None:
    user_id = message.from_user.id
    async with ACTIVE_CHATS_LOCK:
        if user_id in ACTIVE_CHATS:
            ACTIVE_CHATS[user_id]["messages"] = await ensure_system_prompt(user_id, [])
            ACTIVE_CHATS[user_id]["active_session_id"] = None
    logging.info(f"Chat has been reset for {message.from_user.first_name}.")
    await message.answer("✅ Chat reset. You are now in a temporary chat.")


@chat_router.message(Command("chats"))
@perms_allowed
async def command_chat_handler(message: types.Message) -> None:
    user_id = message.from_user.id
    sessions = get_user_chat_sessions(user_id)
    chat_kb = InlineKeyboardBuilder()
    for session_id, name in sessions:
        chat_kb.row(types.InlineKeyboardButton(text=name, callback_data=f"switchchat_{session_id}"))
    if len(sessions) < 10:
        chat_kb.row(types.InlineKeyboardButton(text="➕ New Chat", callback_data="newchat"))
    else:
        chat_kb.row(types.InlineKeyboardButton(text="⚠️ Chats limit reached", callback_data="noop"))
    chat_kb.row(types.InlineKeyboardButton(text="🗑️ Delete Chat", callback_data="deletechat_menu"))
    chat_kb.row(types.InlineKeyboardButton(text="❌ Close", callback_data="close_menu"))
    await message.answer("Chat Management", reply_markup=chat_kb.as_markup())


@chat_router.callback_query(lambda query: query.data == "close_menu")
async def close_menu_handler(query: types.CallbackQuery):
    await query.message.delete()


@chat_router.callback_query(lambda query: query.data == "newchat")
@perms_allowed
async def new_chat_start_handler(query: types.CallbackQuery, state: FSMContext):
    await state.set_state(ChatCreationStates.awaiting_name)
    await query.message.edit_text("Please enter a name for your new chat:")
    await query.answer()


@chat_router.message(ChatCreationStates.awaiting_name)
@perms_allowed
async def chat_name_handler(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    chat_name = message.text.strip()
    if not chat_name:
        await message.reply("The name cannot be empty. Please enter a name for the chat:")
        return

    session_id = create_chat_session(user_id, chat_name)
    await state.clear()
    async with ACTIVE_CHATS_LOCK:
        messages = await ensure_system_prompt(user_id, [])
        ACTIVE_CHATS[user_id] = {
            "active_session_id": session_id,
            "model": modelname,
            "messages": messages,
            "stream": True,
        }
    await message.reply(f"✅ Chat '{chat_name}' created. This conversation will now be saved.")


@chat_router.callback_query(lambda query: query.data.startswith("switchchat_"))
@perms_allowed
async def switch_chat_handler(query: types.CallbackQuery):
    session_id = query.data.split("_")[1]
    user_id = query.from_user.id
    history = load_chat_history(session_id)
    async with ACTIVE_CHATS_LOCK:
        messages = await ensure_system_prompt(user_id, history)
        ACTIVE_CHATS[user_id] = {
            "active_session_id": session_id,
            "model": modelname,
            "messages": messages,
            "stream": True,
        }
    await query.message.edit_text("✅ Chat loaded successfully.")
    await query.answer()


@chat_router.callback_query(lambda query: query.data == "deletechat_menu")
@perms_admins
async def delete_chat_menu_handler(query: types.CallbackQuery):
    user_id = query.from_user.id
    sessions = get_user_chat_sessions(user_id)
    delete_kb = InlineKeyboardBuilder()
    for session_id, name in sessions:
        delete_kb.row(
            types.InlineKeyboardButton(
                text=f"🗑️ {name}", callback_data=f"delete_session_{session_id}"
            )
        )
    delete_kb.row(types.InlineKeyboardButton(text="⬅️ Back", callback_data="chat_menu_main"))
    await query.message.edit_text("Select a chat to delete:", reply_markup=delete_kb.as_markup())
    await query.answer()


@chat_router.callback_query(lambda query: query.data == "chat_menu_main")
async def chat_menu_main_handler(query: types.CallbackQuery):
    # This handler needs access to the original message to re-trigger the command
    # A better approach will be designed in the final step.
    # For now, we just call the function directly.
    await command_chat_handler(query.message)
    await query.answer()


@chat_router.callback_query(lambda query: query.data.startswith("delete_session_"))
@perms_admins
async def delete_session_handler(query: types.CallbackQuery):
    session_id = query.data.split("_")[2]
    user_id = query.from_user.id
    if delete_chat_session(session_id, user_id):
        async with ACTIVE_CHATS_LOCK:
            if ACTIVE_CHATS.get(user_id, {}).get("active_session_id") == session_id:
                ACTIVE_CHATS[user_id]["active_session_id"] = None
                ACTIVE_CHATS[user_id]["messages"] = await ensure_system_prompt(user_id, [])
        await query.answer("Chat deleted successfully.")
    else:
        await query.answer("Failed to delete chat.")
    # This re-triggers the delete menu.
    await delete_chat_menu_handler(query)
