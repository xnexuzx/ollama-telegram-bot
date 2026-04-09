"""
Spinner animation manager for Telegram bot responses.

This module provides the SpinnerManager class to handle animated spinner
indicators during long-running operations (e.g., Ollama API calls).
"""

import time
import logging
from typing import TYPE_CHECKING

from aiogram import types
from aiogram.enums import ParseMode

if TYPE_CHECKING:
    from aiogram import Bot

logger = logging.getLogger(__name__)


class SpinnerManager:
    """
    Manages spinner animations for user interactions.

    Handles the lifecycle of a spinner message: creation, periodic updates,
    smooth transitions to content mode, and cleanup on errors.

    Attributes:
        bot: The aiogram Bot instance
        _state: Dictionary mapping user_id to spinner state dict
    """

    # Class-level constants for spinner configuration
    FRAMES = [".", "..", "..."]
    INTERVAL_PURE = 3.0  # Seconds between updates when only spinner is shown
    INTERVAL_WITH_CONTENT = 2.0  # Seconds between updates with content
    INTERVAL_PARAGRAPH = 1.0  # Seconds after paragraph break

    def __init__(self, bot: "Bot") -> None:
        """
        Initialize the SpinnerManager.

        Args:
            bot: The aiogram Bot instance used to send/edit messages
        """
        self.bot = bot
        self._state: dict[int, dict] = {}

    def get_state(self, user_id: int) -> dict:
        """
        Get or create spinner state for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            State dictionary with keys: spinner_index, last_update, mode, sent_message
        """
        if user_id not in self._state:
            self._state[user_id] = {
                "spinner_index": 0,
                "last_update": 0.0,
                "mode": "pure",  # 'pure' | 'content'
                "sent_message": None,
            }
        return self._state[user_id]

    def reset(self, user_id: int) -> None:
        """
        Reset spinner state for a user.

        Args:
            user_id: Telegram user ID
        """
        if user_id in self._state:
            del self._state[user_id]

    def cleanup_old_entries(self, max_entries: int = 1000) -> None:
        """
        Remove spinner states for users that no longer have active chats.

        This prevents memory leaks by cleaning up orphaned spinner states.

        Args:
            max_entries: Maximum number of states to keep (FIFO cleanup)
        """
        if len(self._state) > max_entries:
            # Remove oldest entries (simple FIFO)
            users_to_remove = list(self._state.keys())[: len(self._state) - max_entries]
            for user_id in users_to_remove:
                del self._state[user_id]
            logger.info(f"Cleaned up {len(users_to_remove)} orphaned spinner states")

    async def update(
        self,
        message: types.Message,
        full_response: str = "",
        force_mode: str = None,
    ) -> types.Message | None:
        """
        Update the spinner animation based on current mode and interval.

        Args:
            message: Original user message (used for chat_id)
            full_response: Accumulated response text so far (empty = pure mode)
            force_mode: Optional mode override ('pure' or 'content')

        Returns:
            The sent/updated message object, or None if no update was needed
        """
        state = self.get_state(message.from_user.id)
        current_time = time.time()

        # Determine current mode
        if force_mode:
            mode = force_mode
        else:
            mode = "pure" if not full_response.strip() else "content"

        # Calculate interval based on mode
        interval = self.INTERVAL_PURE if mode == "pure" else self.INTERVAL_WITH_CONTENT

        # Check if update is needed
        if current_time - state["last_update"] < interval:
            return state["sent_message"]

        # Build spinner text
        current_frame = self.FRAMES[state["spinner_index"]]
        if mode == "pure":
            text = f"`{current_frame}`"
        else:
            text = f"{full_response.strip()}\n\n`{current_frame}`"

        # Send or edit message
        if state["sent_message"] is None:
            state["sent_message"] = await self.bot.send_message(
                chat_id=message.chat.id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            if state["sent_message"].text != text:
                try:
                    await self.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=state["sent_message"].message_id,
                        text=text,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as e:
                    logger.warning(f"Could not edit spinner: {e}")

        # Update state
        state["last_update"] = current_time
        state["spinner_index"] = (state["spinner_index"] + 1) % len(self.FRAMES)
        state["mode"] = mode

        return state["sent_message"]

    async def transition_to_content(
        self, message: types.Message, full_response: str
    ) -> types.Message | None:
        """
        Smoothly transition from pure spinner to content mode.

        This is called when the first content chunk arrives. It combines
        the initial content with the current spinner frame for a seamless
        visual transition.

        Args:
            message: Original user message
            full_response: First chunk of response text

        Returns:
            Updated message object, or None if state doesn't exist
        """
        state = self._state.get(message.from_user.id)
        if not state:
            return None

        current_frame = self.FRAMES[state["spinner_index"]]
        text = f"{full_response.strip()}\n\n`{current_frame}`"

        if state["sent_message"] is None:
            state["sent_message"] = await self.bot.send_message(
                chat_id=message.chat.id,
                text=text,
                parse_mode=ParseMode.MARKDOWN,
            )
        else:
            if state["sent_message"].text != text:
                try:
                    await self.bot.edit_message_text(
                        chat_id=message.chat.id,
                        message_id=state["sent_message"].message_id,
                        text=text,
                        parse_mode=ParseMode.MARKDOWN,
                    )
                except Exception as e:
                    logger.warning(f"Could not transition spinner: {e}")

        state["mode"] = "content"
        state["last_update"] = time.time()
        return state["sent_message"]

    async def delete_if_exists(self, message: types.Message) -> None:
        """
        Delete the spinner message if it exists.

        Used for cleanup when an error occurs.

        Args:
            message: Original user message (used for chat_id)
        """
        state = self._state.get(message.from_user.id)
        if state and state.get("sent_message"):
            try:
                await self.bot.delete_message(
                    chat_id=message.chat.id,
                    message_id=state["sent_message"].message_id,
                )
            except Exception as e:
                logger.warning(f"Could not delete spinner: {e}")

    def get_mode(self, user_id: int) -> str:
        """
        Get current mode for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            Current mode ('pure' or 'content'), or 'pure' if no state exists
        """
        state = self._state.get(user_id)
        return state["mode"] if state else "pure"

    def get_spinner_index(self, user_id: int) -> int:
        """
        Get current spinner frame index for a user.

        Args:
            user_id: Telegram user ID

        Returns:
            Current spinner index (0 to len(FRAMES)-1), or 0 if no state
        """
        state = self._state.get(user_id)
        return state["spinner_index"] if state else 0

    def set_spinner_index(self, user_id: int, index: int) -> None:
        """
        Set spinner frame index for a user.

        Args:
            user_id: Telegram user ID
            index: Spinner frame index (will be modulo'd by FRAMES length)
        """
        state = self._state.get(user_id)
        if state:
            state["spinner_index"] = index % len(self.FRAMES)
