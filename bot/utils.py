import tiktoken


def count_tokens(text: str) -> int:
    """
    Counts the number of tokens in a given text.

    This function tries to use the 'tiktoken' library for an accurate count.
    If 'tiktoken' fails (e.g., due to an unsupported model encoding),
    it falls back to a simple word-based estimation.

    Args:
        text: The input string.

    Returns:
        The estimated number of tokens.
    """
    try:
        # The "cl100k_base" encoding is widely used by many popular models.
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except Exception:
        # Fallback to a simple heuristic if tiktoken fails.
        # This is not perfectly accurate but provides a reasonable estimate.
        return len(text.split())


def find_safe_split_pos(text: str, max_length: int) -> int:
    """
    Finds a safe position to split a string to not exceed max_length.

    It prioritizes splitting at code blocks, paragraphs, newlines,
    sentence ends, or spaces to avoid breaking words or formatting.

    Args:
        text: The text to be split.
        max_length: The maximum desired length for the split.

    Returns:
        The integer position where the text should be split.
    """
    if len(text) <= max_length:
        return len(text)

    # Try to find a split position in order of preference
    split_delimiters = ["\n```", "\n\n", "\n", ". ", " "]
    split_pos = -1

    for delimiter in split_delimiters:
        pos = text[:max_length].rfind(delimiter)
        if pos != -1:
            # Adjust position to be after the delimiter
            if delimiter == ". ":
                split_pos = pos + 1
            else:
                split_pos = pos
            break

    # If no preferred split point is found, force a split at max_length
    if split_pos == -1:
        split_pos = max_length

    return split_pos


def smart_split(text: str, max_length: int = 4000) -> list[str]:
    """
    Splits a long text into smaller chunks using a safe splitting logic.

    Args:
        text: The text to split.
        max_length: The maximum length of each chunk.

    Returns:
        A list of text chunks.
    """
    if len(text) <= max_length:
        return [text]

    chunks = []
    while len(text) > 0:
        if len(text) <= max_length:
            chunks.append(text)
            break

        split_pos = find_safe_split_pos(text, max_length)
        chunks.append(text[:split_pos].strip())
        text = text[split_pos:].lstrip()

    return chunks
