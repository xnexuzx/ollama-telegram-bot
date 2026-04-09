import os
import logging
import io
import base64
import time
import aiohttp
import asyncio
from aiogram import types, Router
from aiogram.enums import ParseMode
from aiogram.filters.command import Command, CommandStart
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.auth import perms_allowed
from bot.core.database import get_global_prompts, update_user_prompt, save_chat_message
from bot.core.ollama import generate, model_supports_vision
from bot.ui import start_kb
from bot.utils import smart_split
from system_prompts import get_all_system_prompts

# WARNING: Circular dependencies. This is a temporary step in refactoring.
# These state variables will be managed properly in the next steps.
from bot import state
from bot.state import (
    bot,
    ACTIVE_CHATS,
    mention,
    get_bot_info,
    ensure_system_prompt,
    cleanup_inactive_chats,
)

user_router = Router()


# --- Basic Commands ---


@user_router.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    """
    Handle the /start command.

    Sends a welcome message with the user's name and the main keyboard.
    """
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
    """
    Handle the /history command.

    Displays the current conversation history for the user in Markdown format.
    """
    if message.from_user.id in ACTIVE_CHATS:
        messages = ACTIVE_CHATS.get(message.from_user.id)["messages"]
        context = ""
        for msg in messages:
            context += f"*{msg['role'].capitalize()}*: {msg['content']}\n"
        await message.answer(context, parse_mode=ParseMode.MARKDOWN)
    else:
        await message.answer("No chat history available for this user")


@user_router.callback_query(lambda query: query.data == "about")
async def about_callback_handler(query: types.CallbackQuery) -> None:
    """
    Handle the 'About' callback from the start menu.

    Shows bot information: current model, default model, license and source code link.
    """
    dotenv_model = os.getenv("INITMODEL")
    await query.message.answer(
        f"<b>Your LLMs</b>\nCurrently using: <code>{state.modelname}</code>\nDefault in .env: <code>{dotenv_model}</code>\nThis project is under <a href='https://github.com/ruecat/ollama-telegram/blob/main/LICENSE'>MIT License.</a>\n<a href='https://github.com/ruecat/ollama-telegram'>Source Code</a>",
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
    )


# --- Prompt Selection ---


@user_router.message(Command("prompts"))
@perms_allowed
async def prompts_command_handler(message: types.Message) -> None:
    """
    Handle the /prompts command.

    Displays an inline keyboard with all available system prompts
    (predefined from system_prompts.py and custom from database).
    """
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
async def select_prompt_handler(query: types.CallbackQuery) -> None:
    """
    Handle prompt selection from the /prompts menu.

    Supports both predefined prompts (from system_prompts.py) and
    custom prompts (from database). Selection is persisted to user profile.
    """
    user_id = query.from_user.id
    parts = query.data.split("_")
    prompt_type = parts[1]
    prompt_key = "_".join(parts[2:])

    if prompt_type == "custom":
        prompt_id_to_save = prompt_key  # Save as string
        prompts = get_global_prompts()
        prompt_name = "Unknown"
        for p_id, name, _ in prompts:
            if str(p_id) == prompt_id_to_save:
                prompt_name = name
                break
        update_user_prompt(user_id, prompt_id_to_save)
        await query.answer(f"System prompt changed to: {prompt_name}")
        await query.message.edit_text(f"✅ System prompt changed to: {prompt_name} (persistent)")

    elif prompt_type == "predefined":
        predefined_prompts = get_all_system_prompts()
        if prompt_key in predefined_prompts:
            prompt_name = predefined_prompts[prompt_key]["name"]
            # Save the predefined key as string (None for default, string key for others)
            prompt_value = None if prompt_key == "default" else prompt_key
            update_user_prompt(user_id, prompt_value)
            await query.answer(f"System prompt changed to: {prompt_name}")
            await query.message.edit_text(
                f"✅ System prompt changed to: {prompt_name} (persistent)"
            )
        else:
            await query.answer("Unknown predefined prompt.", show_alert=True)


@user_router.callback_query(lambda query: query.data == "close_prompt_menu")
async def cancel_prompt_handler(query: types.CallbackQuery) -> None:
    """
    Close the prompts menu by deleting the message.
    """
    await query.message.delete()


# --- Main Message Handling Logic ---


@user_router.message()
@perms_allowed
async def handle_message(message: types.Message) -> None:
    """
    Main message handler for all authorized users.

    Routes messages to ollama_request based on chat type:
    - Private chats: direct processing
    - Groups/supergroups: only if bot is mentioned or replied to
    """
    await get_bot_info()
    if message.chat.type == "private":
        await ollama_request(message)
        return
    if await is_mentioned_in_group_or_supergroup(message):
        thread = await collect_message_thread(message)
        prompt = format_thread_for_prompt(thread)
        await ollama_request(message, prompt)


async def is_mentioned_in_group_or_supergroup(message: types.Message) -> bool:
    """
    Check if the bot is mentioned in a group/supergroup message.

    Returns True if:
    - Message starts with bot's mention
    - Message is a reply to the bot
    """
    if message.chat.type not in ["group", "supergroup"]:
        return False
    is_mentioned = (message.text and message.text.startswith(mention)) or (
        message.caption and message.caption.startswith(mention)
    )
    is_reply_to_bot = message.reply_to_message and message.reply_to_message.from_user.id == bot.id
    return is_mentioned or is_reply_to_bot


async def collect_message_thread(message: types.Message, thread=None) -> list:
    """
    Recursively collect the reply thread for a message.

    Args:
        message: The starting message
        thread: Accumulator for recursion (internal)

    Returns:
        List of messages in chronological order (oldest first)
    """
    if thread is None:
        thread = []
    thread.insert(0, message)
    if message.reply_to_message:
        await collect_message_thread(message.reply_to_message, thread)
    return thread


def format_thread_for_prompt(thread) -> str:
    """
    Format a thread of messages into a prompt for the LLM.

    Args:
        thread: List of message objects

    Returns:
        Formatted string with sender and content for each message
    """
    prompt = "Conversation thread:\n\n"
    for msg in thread:
        sender = "User" if msg.from_user.id != bot.id else "Bot"
        content = msg.text or msg.caption or "[No text content]"
        prompt += f"{sender}: {content}\n\n"
    prompt += "History:"
    return prompt


async def process_image(message: types.Message) -> str:
    """
    Extract and encode image from message if present.

    Args:
        message: Telegram message that may contain a photo

    Returns:
        Base64-encoded image string, or empty string if no image
    """
    image_base64 = ""
    if message.content_type == "photo":
        image_buffer = io.BytesIO()
        await bot.download(message.photo[-1], destination=image_buffer)
        image_base64 = base64.b64encode(image_buffer.getvalue()).decode("utf-8")
    return image_base64


async def add_prompt_to_active_chats(
    message: types.Message, prompt: str, image_base64: str, modelname: str
):
    """
    Add a user message (with optional image) to the active chat history.

    Ensures system prompt is at the beginning and updates last_activity timestamp.
    """
    user_id = message.from_user.id
    if user_id not in ACTIVE_CHATS:
        ACTIVE_CHATS[user_id] = {
            "active_session_id": None,
            "model": state.modelname,
            "messages": [],
            "stream": True,
            "last_activity": time.time(),
        }
    else:
        ACTIVE_CHATS[user_id]["last_activity"] = time.time()
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


async def handle_response(message: types.Message, response_data: dict, full_response: str) -> bool:
    """
    Handle the final response from Ollama.

    Args:
        message: Original user message
        response_data: Response payload from Ollama
        full_response: Complete response text

    Returns:
        True if response was handled (done=True), False otherwise
    """
    full_response_stripped = full_response.strip()
    if full_response_stripped == "":
        return False
    if response_data.get("done"):
        if ACTIVE_CHATS.get(message.from_user.id) is not None:
            ACTIVE_CHATS[message.from_user.id]["messages"].append(
                {"role": "assistant", "content": full_response_stripped}
            )
        logging.info(
            f"[Response]: '{full_response_stripped}' for {message.from_user.first_name} {message.from_user.last_name}"
        )
        return True
    return False


async def ollama_request(message: types.Message, prompt: str = None):
    """
    Main request handler for interacting with Ollama API.

    Args:
        message: Telegram message from user
        prompt: Optional explicit prompt (used for group thread context)

    Flow:
        1. Cleanup inactive chats if threshold exceeded
        2. Extract image if present and validate vision support
        3. Build payload with system prompt, user message, and images
        4. Stream response from Ollama with progressive editing
        5. Handle errors with specific user-friendly messages
        6. Save assistant response to chat history
    """
    try:
        # Limpieza automática de chats inactivos (umbral: 100 entradas)
        if len(ACTIVE_CHATS) > 100:
            cleanup_inactive_chats(timeout_hours=12)

        full_response = ""
        sent_message = None
        await bot.send_chat_action(message.chat.id, "typing")
        image_base64 = await process_image(message)

        # Validate image support if an image was provided
        if image_base64:
            if not model_supports_vision(state.modelname):
                await bot.send_message(
                    chat_id=message.chat.id,
                    text=f"❌ The model '{state.modelname}' does not support image input. "
                    f"Please switch to a vision-capable model using /settings.",
                    parse_mode=ParseMode.HTML,
                )
                return

        if prompt is None:
            prompt = message.text or message.caption
        session_id = ACTIVE_CHATS.get(message.from_user.id, {}).get("active_session_id")
        save_chat_message(message.from_user.id, session_id, "user", prompt)
        await add_prompt_to_active_chats(message, prompt, image_base64, state.modelname)
        logging.info(
            f"[OllamaAPI]: Processing '{prompt}' for {message.from_user.first_name} {message.from_user.last_name}"
        )
        payload = ACTIVE_CHATS.get(message.from_user.id)

        # Reset spinner state for this user
        state.spinner_manager.reset(message.from_user.id)

        async for response_data in generate(payload, state.modelname, prompt):
            msg = response_data.get("message")

            # Update spinner independently of content (time-based)
            sent_message = await state.spinner_manager.update(message, full_response)

            if msg is None:
                continue
            chunk = msg.get("content", "")
            full_response += chunk

            # Transition to content mode on first token
            if state.spinner_manager.get_mode(message.from_user.id) == "pure" and full_response.strip():
                sent_message = await state.spinner_manager.transition_to_content(message, full_response)

            # Handle paragraph breaks for faster updates
            has_paragraph_break = chunk.endswith("\n\n") or "\n\n" in chunk
            if has_paragraph_break:
                # Force immediate update with faster interval
                sent_message = await state.spinner_manager.update(
                    message, full_response, force_mode="content"
                )

            if sent_message is None and full_response.strip():
                # Fallback: send initial message with spinner if not sent yet
                initial_text = f"{full_response.strip()}\n\n`{state.spinner_manager.FRAMES[0]}`"
                sent_message = await bot.send_message(
                    chat_id=message.chat.id,
                    text=initial_text,
                    parse_mode=ParseMode.MARKDOWN,
                )

            if response_data.get("done"):
                # Final response: remove spinner and send complete message(s)
                final_text = f"{full_response.strip()}\n\n⚡ `{state.modelname} in {response_data.get('total_duration') / 1e9:.1f}s.`"
                message_chunks = smart_split(final_text)
                if len(message_chunks) == 1:
                    await bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=sent_message.message_id,
                        text=message_chunks[0],
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
                            chat_id=message.chat.id,
                            text=chunk,
                            parse_mode=ParseMode.MARKDOWN,
                        )
                await handle_response(message, response_data, full_response)
                session_id = ACTIVE_CHATS.get(message.from_user.id, {}).get("active_session_id")
                save_chat_message(
                    message.from_user.id, session_id, "assistant", full_response.strip()
                )
                break
    except aiohttp.ClientResponseError as e:
        # Error HTTP específico (404, 500, etc.)
        logging.error(f"Ollama HTTP error {e.status}: {e.message}", exc_info=True)

        # Limpiar spinner si existe
        await state.spinner_manager.delete_if_exists(message)

        # Mensaje específico según código HTTP
        if e.status == 404:
            error_msg = f"❌ Model '{state.modelname}' not found. Use /settings to download or switch models."
        elif e.status == 500:
            error_msg = "❌ Ollama server error. The model may be corrupted or unavailable."
        else:
            error_msg = f"❌ Ollama returned HTTP {e.status}. Please check the server logs."

        await bot.send_message(
            chat_id=message.chat.id,
            text=error_msg,
            parse_mode=ParseMode.HTML,
        )
    except aiohttp.ClientError as e:
        # Otros errores de conexión (conexión rechazada, timeout de conexión, etc.)
        logging.error(f"Ollama connection error: {e}", exc_info=True)

        # Limpiar spinner si existe
        await state.spinner_manager.delete_if_exists(message)

        error_msg = "❌ Cannot connect to Ollama. Please check if the server is running at the configured URL."
        await bot.send_message(
            chat_id=message.chat.id,
            text=error_msg,
            parse_mode=ParseMode.HTML,
        )
    except asyncio.TimeoutError:
        # Timeout general
        logging.error("Ollama request timeout", exc_info=True)

        # Limpiar spinner si existe
        await state.spinner_manager.delete_if_exists(message)

        error_msg = (
            "❌ Ollama is taking too long to respond. Try a shorter prompt or check the model."
        )
        await bot.send_message(
            chat_id=message.chat.id,
            text=error_msg,
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        # Cualquier otro error inesperado
        logging.error(f"Unexpected error in ollama_request: {e}", exc_info=True)

        # Limpiar spinner si existe
        await state.spinner_manager.delete_if_exists(message)

        error_msg = "❌ An unexpected error occurred. The incident has been logged."
        await bot.send_message(
            chat_id=message.chat.id,
            text=error_msg,
            parse_mode=ParseMode.HTML,
        )
