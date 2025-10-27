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

async def manage_model(action: str, model_name: str):
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