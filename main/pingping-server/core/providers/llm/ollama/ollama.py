from config.logger import setup_logging
from openai import OpenAI
import httpx
import json
from core.providers.llm.base import LLMProviderBase

TAG = __name__
logger = setup_logging()


class LLMProvider(LLMProviderBase):
    def __init__(self, config):
        self.model_name = config.get("model_name")
        self.base_url = config.get("base_url", "http://localhost:11434")
        # Get API key from config if provided (for Ollama instances with authentication enabled)
        self.api_key = config.get("api_key")
        
        # Initialize OpenAI client with Ollama base URL
        # If v1 is not present, add v1
        if not self.base_url.endswith("/v1"):
            self.base_url = f"{self.base_url}/v1"

        # Create a custom HTTP client that doesn't send Authorization header if no api_key
        # This is needed because Ollama without authentication rejects the "Bearer ollama" header
        if self.api_key:
            # If api_key is provided, use it normally
            self.client = OpenAI(
                base_url=self.base_url,
                api_key=self.api_key,
            )
        else:
            # If no api_key, create a custom httpx client that removes Authorization header
            # Override the send method to remove Authorization header before sending
            class NoAuthClient(httpx.Client):
                def send(self, request, **kwargs):
                    # Remove Authorization header if present
                    if 'Authorization' in request.headers:
                        request.headers.pop('Authorization')
                    return super().send(request, **kwargs)
            
            custom_http_client = NoAuthClient(
                timeout=httpx.Timeout(300.0, connect=10.0),
            )
            self.client = OpenAI(
                base_url=self.base_url,
                api_key="",  # Placeholder, will be removed by custom client
                http_client=custom_http_client,
            )

        # Check if it's a qwen3 model
        self.is_qwen3 = self.model_name and self.model_name.lower().startswith("qwen3")

    def response(self, session_id, dialogue, **kwargs):
        try:
            # If it's a qwen3 model, add /no_think instruction to the last user message
            if self.is_qwen3:
                # Copy dialogue list to avoid modifying the original
                dialogue_copy = dialogue.copy()

                # Find the last user message
                for i in range(len(dialogue_copy) - 1, -1, -1):
                    if dialogue_copy[i]["role"] == "user":
                        # Add /no_think instruction before user message
                        dialogue_copy[i]["content"] = (
                            "/no_think " + dialogue_copy[i]["content"]
                        )
                        logger.bind(tag=TAG).debug(f"Added /no_think instruction for qwen3 model")
                        break

                # Use the modified dialogue
                dialogue = dialogue_copy

            responses = self.client.chat.completions.create(
                model=self.model_name, messages=dialogue, stream=True
            )
            is_active = True
            # Buffer for handling tags that span across chunks
            buffer = ""

            for chunk in responses:
                try:
                    delta = (
                        chunk.choices[0].delta
                        if getattr(chunk, "choices", None)
                        else None
                    )
                    content = delta.content if hasattr(delta, "content") else ""

                    if content:
                        # Add content to buffer
                        buffer += content

                        # Process tags in buffer
                        while "<think>" in buffer and "</think>" in buffer:
                            # Find complete <think></think> tags and remove them
                            pre = buffer.split("<think>", 1)[0]
                            post = buffer.split("</think>", 1)[1]
                            buffer = pre + post

                        # Handle case with only opening tag
                        if "<think>" in buffer:
                            is_active = False
                            buffer = buffer.split("<think>", 1)[0]

                        # Handle case with only closing tag
                        if "</think>" in buffer:
                            is_active = True
                            buffer = buffer.split("</think>", 1)[1]

                        # If currently active and buffer has content, output it
                        if is_active and buffer:
                            yield buffer
                            buffer = ""  # Clear buffer

                except Exception as e:
                    logger.bind(tag=TAG).error(f"Error processing chunk: {e}")

        except Exception as e:
            logger.bind(tag=TAG).error(f"Error in Ollama response generation: {e}")
            yield "[Ollama service response error]"

    def response_with_functions(self, session_id, dialogue, functions=None):
        try:
            # If it's a qwen3 model, add /no_think instruction to the last user message
            if self.is_qwen3:
                # Copy dialogue list to avoid modifying the original
                dialogue_copy = dialogue.copy()

                # Find the last user message
                for i in range(len(dialogue_copy) - 1, -1, -1):
                    if dialogue_copy[i]["role"] == "user":
                        # Add /no_think instruction before user message
                        dialogue_copy[i]["content"] = (
                            "/no_think " + dialogue_copy[i]["content"]
                        )
                        logger.bind(tag=TAG).debug(f"Added /no_think instruction for qwen3 model")
                        break

                # Use the modified dialogue
                dialogue = dialogue_copy

            stream = self.client.chat.completions.create(
                model=self.model_name,
                messages=dialogue,
                stream=True,
                tools=functions,
            )

            is_active = True
            buffer = ""

            for chunk in stream:
                try:
                    delta = (
                        chunk.choices[0].delta
                        if getattr(chunk, "choices", None)
                        else None
                    )
                    content = delta.content if hasattr(delta, "content") else None
                    tool_calls = (
                        delta.tool_calls if hasattr(delta, "tool_calls") else None
                    )

                    # If it's a tool call, pass it directly
                    if tool_calls:
                        yield None, tool_calls
                        continue

                    # Process text content
                    if content:
                        # Add content to buffer
                        buffer += content

                        # Process tags in buffer
                        while "<think>" in buffer and "</think>" in buffer:
                            # Find complete <think></think> tags and remove them
                            pre = buffer.split("<think>", 1)[0]
                            post = buffer.split("</think>", 1)[1]
                            buffer = pre + post

                        # Handle case with only opening tag
                        if "<think>" in buffer:
                            is_active = False
                            buffer = buffer.split("<think>", 1)[0]

                        # Handle case with only closing tag
                        if "</think>" in buffer:
                            is_active = True
                            buffer = buffer.split("</think>", 1)[1]

                        # If currently active and buffer has content, output it
                        if is_active and buffer:
                            yield buffer, None
                            buffer = ""  # Clear buffer
                except Exception as e:
                    logger.bind(tag=TAG).error(f"Error processing function chunk: {e}")
                    continue

        except Exception as e:
            logger.bind(tag=TAG).error(f"Error in Ollama function call: {e}")
            # Safely encode exception message to avoid encoding errors
            try:
                error_msg = str(e)
            except (UnicodeEncodeError, UnicodeDecodeError):
                error_msg = repr(e)
            yield f"[Ollama service response error: {error_msg}]", None
