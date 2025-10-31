# System Prompts para Ollama Telegram Bot
# Archivo dedicado para almacenar las system prompts predefinidas

# Dictionary of available prompts
SYSTEM_PROMPTS = {
    "default": {
        "name": "Default Assistant",
        "prompt": "You are a helpful AI assistant running on a Telegram bot.",
    },
    "code": {
        "name": "Code Assistant",
        "prompt": "You are an expert AI programmer. You only write code, no explanations.",
    },
}


def get_system_prompt(prompt_key="default"):
    """Gets a system prompt by its key."""
    return SYSTEM_PROMPTS.get(prompt_key, SYSTEM_PROMPTS["default"])


def get_all_system_prompts():
    """Gets all predefined system prompts."""
    return SYSTEM_PROMPTS
