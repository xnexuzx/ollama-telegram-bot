import logging
import os
import json
import aiohttp
from aiohttp import ClientTimeout
from dotenv import load_dotenv

load_dotenv()

ollama_base_url = os.getenv("OLLAMA_BASE_URL")
ollama_port = os.getenv("OLLAMA_PORT", "11434")
timeout = os.getenv("TIMEOUT", "3000")

# Cache for model capabilities to avoid repeated API calls
_model_capabilities_cache = {}


async def manage_model(action: str, model_name: str):
    """
    Manage Ollama models (pull or delete).

    Args:
        action: Either "pull" or "delete"
        model_name: Name of the model to manage

    Returns:
        aiohttp.ClientResponse or None if action unsupported
    """
    # Optimized timeout for model management operations
    timeout_config = ClientTimeout(total=600, connect=10)  # 10 min total, 10s connect
    async with aiohttp.ClientSession(timeout=timeout_config) as session:
        url = f"http://{ollama_base_url}:{ollama_port}/api/{action}"

        if action == "pull":
            # Use the exact payload structure from the curl example
            data = json.dumps({"name": model_name})
            headers = {"Content-Type": "application/json"}
            logging.info(f"Pulling model: {model_name}")
            logging.info(f"Request URL: {url}")
            logging.info(f"Request Payload: {data}")

            async with session.post(url, data=data, headers=headers) as response:
                logging.info(f"Pull model response status: {response.status}")
                response_text = await response.text()
                logging.info(f"Pull model response text: {response_text}")
                return response
        elif action == "delete":
            data = json.dumps({"name": model_name})
            headers = {"Content-Type": "application/json"}
            async with session.delete(url, data=data, headers=headers) as response:
                return response
        else:
            logging.error(f"Unsupported model management action: {action}")
            return None


async def model_list():
    """
    Fetch list of available models from Ollama.

    Returns:
        List of model dictionaries from Ollama API, empty list on error
    """
    # Quick timeout for listing models
    timeout_config = ClientTimeout(total=15, connect=5)
    async with aiohttp.ClientSession(timeout=timeout_config) as session:
        url = f"http://{ollama_base_url}:{ollama_port}/api/tags"
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                return data["models"]
            else:
                return []


async def generate(payload: dict, modelname: str, prompt: str):
    """
    Generate response from Ollama API using chat completion.

    Args:
        payload: Dictionary with messages, stream flag, etc.
        modelname: Name of the model to use
        prompt: User prompt (for logging)

    Yields:
        dict: Response chunks from Ollama (streaming) or full response (non-streaming)

    Raises:
        aiohttp.ClientResponseError: On HTTP errors from Ollama
        aiohttp.ClientError: On connection errors
    """
    # Optimized timeout configuration for better resource management
    client_timeout = ClientTimeout(
        total=int(timeout),
        connect=10,  # Connection timeout: 10s
        sock_read=int(timeout),  # Socket read timeout
    )
    async with aiohttp.ClientSession(timeout=client_timeout) as session:
        url = f"http://{ollama_base_url}:{ollama_port}/api/chat"

        # Prepare the payload according to Ollama API specification
        ollama_payload = {
            "model": modelname,
            "messages": payload.get("messages", []),
            "stream": payload.get("stream", True),
        }

        try:
            logging.info(f"Sending request to Ollama API: {url}")
            logging.info(f"Payload: {json.dumps(ollama_payload, indent=2)}")

            async with session.post(url, json=ollama_payload) as response:
                if response.status != 200:
                    error_text = await response.text()
                    logging.error(f"API Error: {response.status} - {error_text}")
                    raise aiohttp.ClientResponseError(
                        request_info=response.request_info,
                        history=response.history,
                        status=response.status,
                        message=f"API Error: {error_text}",
                    )

                # Handle streaming and non-streaming responses
                if ollama_payload.get("stream", True):
                    buffer = b""
                    async for chunk in response.content.iter_any():
                        buffer += chunk
                        while b"\n" in buffer:
                            line, buffer = buffer.split(b"\n", 1)
                            line = line.strip()
                            if line:
                                try:
                                    yield json.loads(line)
                                except json.JSONDecodeError as e:
                                    logging.error(f"JSON Decode Error: {e}")
                                    logging.error(f"Problematic line: {line}")
                else:
                    # Non-streaming: yield the single complete JSON response
                    response_data = await response.json()
                    yield response_data

        except aiohttp.ClientError as e:
            logging.error(f"Client Error during request: {e}")
            raise


async def get_model_capabilities(modelname: str) -> set:
    """
    Fetch model information from Ollama API to determine its capabilities.
    Uses /api/show endpoint. Results are cached in memory.

    Returns:
        set: A set of capability strings (e.g., {"vision", "embedding", ...})
             Returns empty set if capabilities cannot be determined.
    """
    global _model_capabilities_cache

    # Check cache first
    if modelname in _model_capabilities_cache:
        return _model_capabilities_cache[modelname]

    try:
        timeout_config = ClientTimeout(total=10, connect=5)
        async with aiohttp.ClientSession(timeout=timeout_config) as session:
            url = f"http://{ollama_base_url}:{ollama_port}/api/show"
            payload = {"name": modelname}
            async with session.post(url, json=payload) as response:
                if response.status == 200:
                    data = await response.json()
                    # Extract capabilities from model info
                    capabilities = set()
                    model_info = data.get("model", {})
                    # Check for vision/multimodal capabilities
                    if "vision" in model_info.get("capabilities", []):
                        capabilities.add("vision")
                    if "multimodal" in model_info.get("capabilities", []):
                        capabilities.add("multimodal")
                    # Cache the result
                    _model_capabilities_cache[modelname] = capabilities
                    logging.info(f"Model '{modelname}' capabilities: {capabilities}")
                    return capabilities
                else:
                    logging.warning(
                        f"Could not fetch capabilities for '{modelname}': HTTP {response.status}"
                    )
                    _model_capabilities_cache[modelname] = set()
                    return set()
    except Exception as e:
        logging.warning(f"Error fetching capabilities for '{modelname}': {e}")
        _model_capabilities_cache[modelname] = set()
        return set()


def model_supports_vision(modelname: str) -> bool:
    """
    Check if a model supports vision based on known patterns or cached API info.
    This is a quick synchronous check using cached data.

    Returns:
        bool: True if model likely supports vision, False otherwise.
    """
    # Check cache first (from async function)
    if modelname in _model_capabilities_cache:
        return (
            "vision" in _model_capabilities_cache[modelname]
            or "multimodal" in _model_capabilities_cache[modelname]
        )

    # Fallback: check by model name patterns (case-insensitive)
    model_lower = modelname.lower()
    # Common vision model name patterns
    vision_patterns = [
        "llava",
        "bakllava",
        "moondream",
        "vision",
        "vl",  # vision-language
        "multimodal",
        "gemma3",
        "phi4-multimodal",
    ]
    for pattern in vision_patterns:
        if pattern in model_lower:
            return True

    return False
