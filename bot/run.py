import sys
import os
import asyncio
import logging
from aiogram import types

# Add project root to PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import shared state and core functions
from bot.state import bot, dp
from bot.core.database import init_db

# Import routers
from bot.handlers.admin import admin_router
from bot.handlers.chats import chat_router
from bot.handlers.user import user_router

async def main():
    # Initialize database
    init_db()

    # Set bot commands
    commands = [
        types.BotCommand(command="start", description="Start"),
        types.BotCommand(command="settings", description="[Admin] Access bot settings"),
        types.BotCommand(command="prompts", description="Select a system prompt"),
        types.BotCommand(command="chats", description="Manage chats"),
        types.BotCommand(command="reset", description="Reset current chat"),
        types.BotCommand(command="history", description="Look through messages"),
        types.BotCommand(command="pullmodel", description="[Admin] Pull a model from Ollama"),
        types.BotCommand(command="adduser", description="[Admin] Add user to allowlist"),
        types.BotCommand(command="rmuser", description="[Admin] Remove user from allowlist"),
        types.BotCommand(command="listusers", description="[Admin] List allowed users"),
    ]
    await bot.set_my_commands(commands)

    # Include routers
    dp.include_router(admin_router)
    dp.include_router(chat_router)
    dp.include_router(user_router) # User router should be last as it has the generic message handler

    # Start polling
    await dp.start_polling(
        bot,
        timeout=50,
        request_timeout=60,
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query"],
    )

if __name__ == "__main__":
    # This is a workaround for a known issue on Windows
    # https://github.com/aio-libs/aiohttp/issues/6444
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())