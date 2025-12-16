import logging
import os
from functools import wraps
from aiogram import types
from dotenv import load_dotenv

from bot.core.database import is_user_allowed

load_dotenv()

admin_ids = list(map(int, os.getenv("ADMIN_IDS", "").split(",")))


def perms_allowed(func):
    @wraps(func)
    async def wrapper(message: types.Message = None, query: types.CallbackQuery = None, **kwargs):
        user_id = message.from_user.id if message else query.from_user.id
        # Check against DB directly, and also check admin_ids from .env
        if user_id in admin_ids or is_user_allowed(user_id):
            if message:
                return await func(message, **kwargs)
            elif query:
                return await func(query=query, **kwargs)
        else:
            if message:
                # In groups, stay silent to avoid spam. In private, show access denied.
                if message.chat.type in ["supergroup", "group"]:
                    return
                await message.answer("Access Denied")
            elif query:
                await query.answer("Access Denied")

    return wrapper


def perms_admins(func):
    @wraps(func)
    async def wrapper(message: types.Message = None, query: types.CallbackQuery = None, **kwargs):
        user_id = message.from_user.id if message else query.from_user.id
        if user_id in admin_ids:
            if message:
                return await func(message, **kwargs)
            elif query:
                return await func(query=query, **kwargs)
        else:
            if message:
                if message and message.chat.type in ["supergroup", "group"]:
                    return
                await message.answer("Access Denied")
                logging.info(
                    f"[MSG] {message.from_user.first_name} {message.from_user.last_name}({message.from_user.id}) is not allowed to use this bot."
                )
            elif query:
                if message and message.chat.type in ["supergroup", "group"]:
                    return
                await query.answer("Access Denied")
                logging.info(
                    f"[QUERY] {query.from_user.first_name} {query.from_user.last_name}({query.from_user.id}) is not allowed to use this bot."
                )

    return wrapper
