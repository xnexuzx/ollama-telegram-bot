"""
Utility functions for the Ollama Telegram bot.
"""

from bot.utils.spinner import SpinnerManager
from bot.utils.text import find_safe_split_pos, smart_split


def count_tokens(text: str, model: str | None = None) -> int:
    """Count tokens in a text string using tiktoken if available, else fallback.

    Args:
        text: The text to count tokens for.
        model: Optional model name to use appropriate encoding.

    Returns:
        Number of tokens in the text.
    """
    try:
        import tiktoken

        if model:
            try:
                encoding = tiktoken.encoding_for_model(model)
            except KeyError:
                # Fallback to cl100k_base for unknown models
                encoding = tiktoken.get_encoding("cl100k_base")
        else:
            encoding = tiktoken.get_encoding("cl100k_base")

        return len(encoding.encode(text))
    except ImportError:
        # Fallback: approximate 1 token per 4 characters
        return max(1, len(text) // 4)


__all__ = ["SpinnerManager", "find_safe_split_pos", "smart_split", "count_tokens"]
