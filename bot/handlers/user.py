import os
import logging
import traceback
import io
import base64
import time
from aiogram import types, Router
from aiogram.enums import ParseMode
from aiogram.filters.command import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.auth import perms_allowed
from bot.core.database import get_global_prompts, update_user_prompt, save_chat_message
from bot.core.ollama import generate
from bot.ui import start_kb
from bot.utils import find_safe_split_pos, smart_split
from system_prompts import get_all_system_prompts

# WARNING: Circular dependencies. This is a temporary step in refactoring.
# These state variables will be managed properly in the next steps.
from bot import state
from bot.state import (
    bot,
    ACTIVE_CHATS,
    ACTIVE_CHATS_LOCK,
    mention,
    get_bot_info,
    ensure_system_prompt,
)

user_router = Router()

SPINNER_FRAMES = [".", "..", "..."]

# --- Basic Commands ---


@user_router.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    start_message = f"Welcome, <b>{message.from_user.full_name}</b>!"
    await message.answer(
        start_message,
        parse_mode=ParseMode.HTML,
        reply_markup=start_kb.as_markup(),
        disable_web_page_preview=True,
    )


@user_router.message(Command("history"))
@perms_allowed
async def command_get_context_handler(message: types.Message) -> None:
    if message.from_user.id in ACTIVE_CHATS:
        messages = ACTIVE_CHATS.get(message.from_user.id)["messages"]
        context = ""
        for msg in messages:
            context += f"*{msg['role'].capitalize()}*: {msg['content']}\n"
        await message.answer(context, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.answer("No chat history available for this user")


@user_router.callback_query(lambda query: query.data == "about")
async def about_callback_handler(query: types.CallbackQuery):
    dotenv_model = os.getenv("INITMODEL")
    await query.message.answer(
        f"<b>Your LLMs</b>\nCurrently using: <code>{state.modelname}</code>\nDefault in .env: <code>{dotenv_model}</code>\nThis project is under <a href='https://github.com/ruecat/ollama-telegram/blob/main/LICENSE'>MIT License.</a>\n<a href='https://github.com/ruecat/ollama-telegram'>Source Code</a>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


# --- Prompt Selection ---


@user_router.message(Command("prompts"))
@perms_allowed
async def prompts_command_handler(message: types.Message):
    prompts_kb = InlineKeyboardBuilder()

    # Add predefined system prompts from system_prompts.py
    predefined_prompts = get_all_system_prompts()
    for key, value in predefined_prompts.items():
        prompts_kb.row(
            types.InlineKeyboardButton(
                text=f"🤖 {value['name']}", callback_data=f"select_predefined_{key}"
            )
        )

    # Add custom prompts from the database
    custom_prompts = get_global_prompts()
    for prompt_id, name, _ in custom_prompts:
        prompts_kb.row(
            types.InlineKeyboardButton(
                text=f"👤 {name}", callback_data=f"select_custom_{prompt_id}"
            )
        )

    prompts_kb.row(types.InlineKeyboardButton(text="❌ Close", callback_data="close_prompt_menu"))
    await message.answer("Select a System Prompt:", reply_markup=prompts_kb.as_markup())


@user_router.callback_query(lambda query: query.data.startswith("select_"))
async def select_prompt_handler(query: types.CallbackQuery):
    user_id = query.from_user.id
    parts = query.data.split("_")
    prompt_type = parts[1]
    prompt_key = "_".join(parts[2:])

    if prompt_type == "custom":
        prompt_id_to_save = int(prompt_key)
        prompts = get_global_prompts()
        prompt_name = "Unknown"
        for p_id, name, _ in prompts:
            if p_id == prompt_id_to_save:
                prompt_name = name
                break
        update_user_prompt(user_id, prompt_id_to_save)
        await query.answer(f"System prompt changed to: {prompt_name}")
        await query.message.edit_text(f"✅ System prompt changed to: {prompt_name} (persistent)")

    elif prompt_type == "predefined":
        predefined_prompts = get_all_system_prompts()
        if prompt_key in predefined_prompts:
            prompt_name = predefined_prompts[prompt_key]["name"]

            # Use `None` for the default key to make it persistent via fallback
            if prompt_key == "default":
                update_user_prompt(user_id, None)
                await query.answer(f"System prompt changed to: {prompt_name}")
                await query.message.edit_text(
                    f"✅ System prompt changed to: {prompt_name} (persistent)"
                )
            else:
                # For other predefined prompts, apply for the current session only
                async with ACTIVE_CHATS_LOCK:
                    if user_id not in ACTIVE_CHATS:
                        ACTIVE_CHATS[user_id] = {"messages": []}  # Ensure chat exists

                    messages = ACTIVE_CHATS[user_id].get("messages", [])

                    # Remove old system prompt if it exists
                    if messages and messages[0]["role"] == "system":
                        messages.pop(0)

                    # Add new one
                    new_prompt_text = predefined_prompts[prompt_key]["prompt"]
                    messages.insert(0, {"role": "system", "content": new_prompt_text})
                    ACTIVE_CHATS[user_id]["messages"] = messages

                await query.answer(
                    f"Switched to {prompt_name} for this session only.", show_alert=True
                )
                await query.message.edit_text(f"✅ Switched to: {prompt_name} (session only)")
        else:
            await query.answer("Unknown predefined prompt.", show_alert=True)


@user_router.callback_query(lambda query: query.data == "close_prompt_menu")
async def cancel_prompt_handler(query: types.CallbackQuery):
    await query.message.delete()


# --- Main Message Handling Logic ---


@user_router.message()
@perms_allowed
async def handle_message(message: types.Message):
    await get_bot_info()
    if message.chat.type == "private":
        await ollama_request(message)
        return
    if await is_mentioned_in_group_or_supergroup(message):
        thread = await collect_message_thread(message)
        prompt = format_thread_for_prompt(thread)
        await ollama_request(message, prompt)


async def is_mentioned_in_group_or_supergroup(message: types.Message):
    if message.chat.type not in ["group", "supergroup"]:
        return False
    is_mentioned = (message.text and message.text.startswith(mention)) or (
        message.caption and message.caption.startswith(mention)
    )
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    return is_mentioned or is_reply_to_bot


async def collect_message_thread(message: types.Message, thread=None):
    if thread is None:
        thread = []
    thread.insert(0, message)
    if message.reply_to_message:
        await collect_message_thread(message.reply_to_message, thread)
    return thread


def format_thread_for_prompt(thread):
    prompt = "Conversation thread:\n\n"
    for msg in thread:
        sender = "User" if msg.from_user.id != bot.id else "Bot"
        content = msg.text or msg.caption or "[No text content]"
        prompt += f"{sender}: {content}\n\n"
    prompt += "History:"
    return prompt


async def process_image(message):
    image_base64 = ""
    if message.content_type == "photo":
        image_buffer = io.BytesIO()
        await bot.download(message.photo[-1], destination=image_buffer)
        image_base64 = base64.b64encode(image_buffer.getvalue()).decode("utf-8")
    return image_base64


async def add_prompt_to_active_chats(message, prompt, image_base64, modelname):
    user_id = message.from_user.id
    async with ACTIVE_CHATS_LOCK:
        if user_id not in ACTIVE_CHATS:
            ACTIVE_CHATS[user_id] = {
                "active_session_id": None,
                "model": state.modelname,
                "messages": [],
                "stream": True,
                "spinner_index": 0,
            }
        messages = ACTIVE_CHATS[user_id]["messages"]
        messages = await ensure_system_prompt(user_id, messages)
        messages.append(
            {
                "role": "user",
                "content": prompt,
                "images": ([image_base64] if image_base64 else []),
            }
        )
        ACTIVE_CHATS[user_id]["messages"] = messages


async def handle_response(message, response_data, full_response):
    full_response_stripped = full_response.strip()
    if full_response_stripped == "":
        return False
    if response_data.get("done"):
        async with ACTIVE_CHATS_LOCK:
            if ACTIVE_CHATS.get(message.from_user.id) is not None:
                ACTIVE_CHATS[message.from_user.id]["messages"].append(
                    {"role": "assistant", "content": full_response_stripped}
                )
        logging.info(
            f"[Response]: '{full_response_stripped}' for {message.from_user.first_name} {message.from_user.last_name}"
        )
        return True
    return False


async def edit_message_progressive(message, sent_message, text):
    try:
        await bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=sent_message.message_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as e:
        logging.warning(f"Could not edit message: {e}")


async def ollama_request(message: types.Message, prompt: str = None):
    try:
        full_response = ""
        last_edit_time = 0
        sent_message = None
        await bot.send_chat_action(message.chat.id, "typing")
        image_base64 = await process_image(message)
        if prompt is None:
            prompt = message.text or message.caption
        session_id = ACTIVE_CHATS.get(message.from_user.id, {}).get("active_session_id")
        save_chat_message(message.from_user.id, session_id, "user", prompt)
        await add_prompt_to_active_chats(message, prompt, image_base64, state.modelname)
        logging.info(
            f"[OllamaAPI]: Processing '{prompt}' for {message.from_user.first_name} {message.from_user.last_name}"
        )
        payload = ACTIVE_CHATS.get(message.from_user.id)
        async for response_data in generate(payload, state.modelname, prompt):
            msg = response_data.get("message")
            if msg is None:
                continue
            chunk = msg.get("content", "")
            full_response += chunk
            if sent_message is None:
                initial_text = f"`{SPINNER_FRAMES[0]}`"
                sent_message = await bot.send_message(
                    chat_id=message.chat.id,
                    text=initial_text,
                    parse_mode=ParseMode.MARKDOWN,
                )
                last_edit_time = time.time()
                # Increment spinner index after first use
                user_chat = ACTIVE_CHATS.get(message.from_user.id, {})
                user_chat["spinner_index"] = (user_chat.get("spinner_index", 0) + 1) % len(
                    SPINNER_FRAMES
                )
            current_time = time.time()
            has_paragraph_break = chunk.endswith("\n\n") or "\n\n" in chunk
            should_edit = (current_time - last_edit_time >= 4.0) or (
                has_paragraph_break and current_time - last_edit_time >= 1.0
            )
            if should_edit and not response_data.get("done"):
                display_text = full_response.strip()
                if display_text:
                    # The text to display is the raw response plus the indicator
                    user_chat = ACTIVE_CHATS.get(message.from_user.id, {})
                    spinner_index = user_chat.get("spinner_index", 0)
                    current_spinner_frame = SPINNER_FRAMES[spinner_index]
                    text_to_display = f"{full_response.strip()}\n\n`{current_spinner_frame}`"
                    user_chat["spinner_index"] = (spinner_index + 1) % len(SPINNER_FRAMES)

                    if len(text_to_display) > 4000:
                        # If the display text is too long, find a safe split in the *raw* response
                        split_pos = find_safe_split_pos(full_response, 4000)
                        chunk_to_send = full_response[:split_pos]
                        remaining_text = full_response[split_pos:]

                        await bot.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=sent_message.message_id,
                            text=chunk_to_send.strip(),
                            parse_mode=ParseMode.MARKDOWN,
                        )
                        # Create a new message for the rest of the content
                        sent_message = await bot.send_message(
                            chat_id=message.chat.id,
                            text=f"`{SPINNER_FRAMES[0]}`",  # Initial text for the new message
                            parse_mode=ParseMode.MARKDOWN,
                        )
                        full_response = remaining_text
                    else:
                        await edit_message_progressive(message, sent_message, text_to_display)
                    last_edit_time = current_time
            if response_data.get("done"):
                final_text = f"{full_response.strip()}\n\n⚡ `{state.modelname} in {response_data.get('total_duration') / 1e9:.1f}s.`"
                message_chunks = smart_split(final_text)
                if len(message_chunks) == 1:
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=sent_message.message_id,
                        text=final_text,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                else:
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=sent_message.message_id,
                        text=message_chunks[0],
                        parse_mode=ParseMode.MARKDOWN,
                    )
                    for chunk in message_chunks[1:]:
                        await bot.send_message(
                            chat_id=message.chat.id, text=chunk, parse_mode=ParseMode.MARKDOWN
                        )
                await handle_response(message, response_data, full_response)
                session_id = ACTIVE_CHATS.get(message.from_user.id, {}).get("active_session_id")
                save_chat_message(
                    message.from_user.id, session_id, "assistant", full_response.strip()
                )
                break
    except Exception as e:
        print(f"-----\n[OllamaAPI-ERR] CAUGHT FAULT!\n{traceback.format_exc()}\n-----")
        await bot.send_message(
            chat_id=message.chat.id,
            text=f"Something went wrong: {str(e)}",
            parse_mode=ParseMode.HTML,
        )
