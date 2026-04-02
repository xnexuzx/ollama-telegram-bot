import sqlite3
import uuid
from bot.utils import count_tokens


# From run.py
def init_db() -> None:
    """
    Initialize the SQLite database with all required tables.

    Creates tables: users, chat_sessions, chats, system_prompts, bot_config
    if they don't already exist.
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users
                 (id INTEGER PRIMARY KEY,
                  name TEXT,
                  selected_prompt_id TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS chat_sessions
                 (session_id TEXT PRIMARY KEY,
                  user_id INTEGER,
                  name TEXT,
                  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS chats
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  session_id TEXT,
                  user_id INTEGER,
                  role TEXT,
                  content TEXT,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (session_id) REFERENCES chat_sessions(session_id),
                  FOREIGN KEY (user_id) REFERENCES users(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS system_prompts
                 (id INTEGER PRIMARY KEY AUTOINCREMENT,
                  user_id INTEGER,
                  name TEXT,
                  prompt TEXT,
                  is_global BOOLEAN,
                  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                  FOREIGN KEY (user_id) REFERENCES users(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS bot_config
                 (key TEXT PRIMARY KEY,
                  value TEXT)""")
    conn.commit()
    conn.close()


# From run.py
def save_chat_message(user_id: int, session_id: str | None, role: str, content: str) -> None:
    """
    Save a single chat message to the database.

    Args:
        user_id: Telegram user ID
        session_id: Chat session ID (None for temporary chats)
        role: Message role ("user" or "assistant")
        content: Text content of the message
    """
    if session_id is None:
        return
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO chats (user_id, session_id, role, content) VALUES (?, ?, ?, ?)",
        (user_id, session_id, role, content),
    )
    conn.commit()
    conn.close()


# From func/interactions.py
def add_global_prompt(name: str, prompt_text: str) -> None:
    """
    Add a new global system prompt.

    Args:
        name: Display name for the prompt
        prompt_text: Actual system prompt text
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO system_prompts (name, prompt, is_global) VALUES (?, ?, 1)",
        (name, prompt_text),
    )
    conn.commit()
    conn.close()


# From func/interactions.py
def get_global_prompts() -> list[tuple]:
    """
    Retrieve all global system prompts from database.

    Returns:
        List of tuples: (id, name, prompt) for each global prompt
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT id, name, prompt FROM system_prompts WHERE is_global = 1")
    prompts = c.fetchall()
    conn.close()
    return prompts


# From func/interactions.py
def delete_global_prompt(prompt_id: int) -> None:
    """
    Delete a global system prompt by ID.

    Args:
        prompt_id: ID of the prompt to delete
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("DELETE FROM system_prompts WHERE id = ?", (prompt_id,))
    conn.commit()
    conn.close()


# From func/interactions.py
def load_chat_history(session_id: str, token_limit: int = 4096) -> list[dict]:
    """
    Load chat history from the database for a specific session,
    limited by an approximate token count.
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    # Retrieve messages in reverse chronological order to get the most recent ones first
    c.execute(
        "SELECT role, content FROM chats WHERE session_id = ? ORDER BY timestamp DESC",
        (session_id,),
    )

    history = []
    total_tokens = 0

    all_messages = c.fetchall()
    conn.close()

    # Build the history chronologically by inserting at the beginning
    for role, content in all_messages:
        message_tokens = count_tokens(content)

        if total_tokens + message_tokens > token_limit:
            break

        history.insert(0, {"role": role, "content": content})
        total_tokens += message_tokens

    return history


# From func/interactions.py
def delete_chat_history(user_id: int) -> bool:
    """
    Deletes all chat history for a specific user from the database.
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("DELETE FROM chats WHERE user_id = ?", (user_id,))
    deleted = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted


# From func/interactions.py
def get_all_users_from_db() -> list[tuple]:
    """
    Retrieve all users from the database.

    Returns:
        List of tuples: (id, name, selected_prompt_id) for each user
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    # FIX: Select all 3 columns to prevent unpacking errors in handlers
    c.execute("SELECT id, name, selected_prompt_id FROM users")
    users = c.fetchall()
    conn.close()
    return users


# From func/interactions.py
def remove_user_from_db(user_id: int) -> bool:
    """
    Remove a user from the allowlist.

    Args:
        user_id: Telegram user ID to remove

    Returns:
        bool: True if user was removed, False if not found
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("DELETE FROM users WHERE id = ?", (user_id,))
    removed = c.rowcount > 0
    conn.commit()
    conn.close()
    return removed


# From func/interactions.py
def get_user_chat_sessions(user_id: int) -> list[tuple]:
    """
    Retrieves all chat sessions for a specific user.
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute(
        "SELECT session_id, name FROM chat_sessions WHERE user_id = ? ORDER BY created_at DESC",
        (user_id,),
    )
    sessions = c.fetchall()
    conn.close()
    return sessions


# From func/interactions.py
def create_chat_session(user_id: int, name: str) -> str:
    """
    Creates a new chat session for a user.
    """
    session_id = str(uuid.uuid4())
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute(
        "INSERT INTO chat_sessions (session_id, user_id, name) VALUES (?, ?, ?)",
        (session_id, user_id, name),
    )
    conn.commit()
    conn.close()
    return session_id


# From func/interactions.py
def delete_chat_session(session_id: str, user_id: int) -> bool:
    """
    Deletes a chat session and all its associated messages from the database.
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()

    # Delete messages associated with the session
    c.execute("DELETE FROM chats WHERE session_id = ? AND user_id = ?", (session_id, user_id))

    # Delete the session itself
    c.execute(
        "DELETE FROM chat_sessions WHERE session_id = ? AND user_id = ?",
        (session_id, user_id),
    )

    deleted_sessions = c.rowcount > 0
    conn.commit()
    conn.close()
    return deleted_sessions


# From func/interactions.py
def add_user_to_db(user_id: int, user_name: str) -> bool:
    """
    Adds a user to the 'users' table. Returns True if added, False if already exists.
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    try:
        c.execute("INSERT INTO users (id, name) VALUES (?, ?)", (user_id, user_name))
        conn.commit()
        was_added = True
    except sqlite3.IntegrityError:
        was_added = False  # User already exists
    finally:
        conn.close()
    return was_added


# From func/interactions.py
def update_user_prompt(user_id: int, prompt_id: str | None) -> None:
    """
    Updates the user's selected prompt.
    prompt_id can be:
    - None (for default)
    - A string key for predefined prompts ("default", "code", etc.)
    - A numeric ID for custom prompts (will be converted to string)
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    # Ensure the user exists before trying to update, crucial for admins.
    c.execute("INSERT OR IGNORE INTO users (id, name) VALUES (?, ?)", (user_id, f"User {user_id}"))
    # Convert to string for storage (None becomes NULL)
    prompt_id_str = str(prompt_id) if prompt_id is not None else None
    c.execute("UPDATE users SET selected_prompt_id = ? WHERE id = ?", (prompt_id_str, user_id))
    conn.commit()
    conn.close()


# From func/interactions.py
def get_user_prompt(user_id: int) -> str | None:
    """
    Returns the user's selected prompt identifier.
    Can be:
    - None (no selection, use default)
    - A string key for predefined prompts ("default", "code", etc.)
    - A string representation of a numeric ID for custom prompts
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT selected_prompt_id FROM users WHERE id = ?", (user_id,))
    result = c.fetchone()
    conn.close()
    if result and result[0] is not None:
        return str(result[0])  # Ensure it's returned as string
    return None


# From func/interactions.py
def is_user_allowed(user_id: int) -> bool:
    """
    Checks if a user is in the 'users' table in the database.
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT 1 FROM users WHERE id = ?", (user_id,))
    allowed = c.fetchone() is not None
    conn.close()
    return allowed


# Bot configuration functions
def get_bot_config(key: str) -> str | None:
    """
    Retrieves a configuration value from bot_config table.
    Returns None if key doesn't exist.
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("SELECT value FROM bot_config WHERE key = ?", (key,))
    result = c.fetchone()
    conn.close()
    return result[0] if result else None


def set_bot_config(key: str, value: str):
    """
    Sets or updates a configuration value in bot_config table.
    Uses INSERT OR REPLACE to handle both new and existing keys.
    """
    conn = sqlite3.connect("users.db")
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO bot_config (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()
