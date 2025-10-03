import asyncio
import json
from typing import List, Optional, AsyncIterator, Dict, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, reraise
import logging

from config import (
    Message, OpenRouterRequest, OpenRouterResponse,
    OpenRouterError, RateLimitError, AuthError, TimeoutError, APIError, EnvConfig
)

logger = logging.getLogger(__name__)

class OpenRouterClient:
    """Async client for OpenRouter API with retries, timeouts, and streaming support."""

    def __init__(self, config: EnvConfig):
        self.config = config
        self.base_url = config.OPENROUTER_BASE_URL.rstrip('/')
        self.api_key = config.OPENROUTER_API_KEY
        self.default_model = config.MODEL_DEFAULT
        self._client: Optional[httpx.AsyncClient] = None

    async def __aenter__(self) -> 'OpenRouterClient':
        await self._ensure_client()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def _ensure_client(self) -> None:
        """Ensure httpx client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(60.0),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://github.com/prof-ramos/Oraculo-BOT",
                    "X-Title": "Oraculo-BOT Discord Chatbot"
                }
            )

    async def close(self) -> None:
        """Close the httpx client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _handle_error(self, response: httpx.Response) -> None:
        """Handle API errors based on status code."""
        if response.status_code == 429:
            retry_after = response.headers.get("Retry-After")
            raise RateLimitError(
                status_code=response.status_code,
                detail=f"Rate limit exceeded. Retry after: {retry_after}"
            )
        elif response.status_code in (401, 403):
            raise AuthError(
                status_code=response.status_code,
                detail="Authentication failed. Check API key."
            )
        elif response.status_code >= 500:
            raise APIError(
                status_code=response.status_code,
                detail=f"Server error: {response.text}"
            )
        else:
            raise APIError(
                status_code=response.status_code,
                detail=f"API error: {response.text}"
            )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((RateLimitError, TimeoutError, APIError)),
        reraise=True
    )
    async def query_chat(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        max_tokens: Optional[int] = 1024,
        temperature: Optional[float] = 0.7,
        stream: bool = False
    ) -> str:
        """Query OpenRouter API for chat completion."""
        model = model or self.default_model

        request_data = OpenRouterRequest(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=stream
        )

        await self._ensure_client()

        try:
            logger.info(f"Querying OpenRouter with model {model}", extra={
                "model": model,
                "message_count": len(messages),
                "stream": stream
            })

            response = await self._client.post(
                f"{self.base_url}/chat/completions",
                json=request_data.model_dump()
            )

            if not response.is_success:
                self._handle_error(response)

            result = OpenRouterResponse.model_validate(response.json())

            if not result.choices:
                raise APIError(detail="No choices returned from API")

            content = result.choices[0].message.content

            logger.info(f"OpenRouter query successful", extra={
                "model": model,
                "tokens_used": result.usage.total_tokens if result.usage else None,
                "content_length": len(content)
            })

            return content

        except httpx.TimeoutException as e:
            logger.error(f"Request timeout: {e}")
            raise TimeoutError("Request timed out")
        except httpx.RequestError as e:
            logger.error(f"Request error: {e}")
            raise APIError(detail=f"Request failed: {e}")

    async def stream_chat(
        self,
        messages: List[Message],
        model: Optional[str] = None,
        max_tokens: Optional[int] = 1024,
        temperature: Optional[float] = 0.7
    ) -> AsyncIterator[str]:
        """Stream chat completion from OpenRouter API."""
        model = model or self.default_model

        request_data = OpenRouterRequest(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
            stream=True
        )

        await self._ensure_client()

        try:
            logger.info(f"Starting OpenRouter stream with model {model}", extra={
                "model": model,
                "message_count": len(messages)
            })

            async with self._client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                json=request_data.model_dump()
            ) as response:

                if not response.is_success:
                    self._handle_error(response)

                # Parse SSE stream
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:].strip()
                        if data == "[DONE]":
                            break

                        try:
                            chunk = json.loads(data)
                            if chunk.get("choices") and chunk["choices"][0].get("delta", {}).get("content"):
                                content = chunk["choices"][0]["delta"]["content"]
                                yield content
                        except json.JSONDecodeError:
                            continue

            logger.info(f"OpenRouter stream completed for model {model}")

        except httpx.TimeoutException as e:
            logger.error(f"Stream timeout: {e}")
            raise TimeoutError("Stream timed out")
        except httpx.RequestError as e:
            logger.error(f"Stream request error: {e}")
            raise APIError(detail=f"Stream request failed: {e}")

    async def get_models(self) -> List[Dict[str, Any]]:
        """Get available models from OpenRouter."""
        await self._ensure_client()

        try:
            response = await self._client.get(f"{self.base_url}/models")

            if not response.is_success:
                self._handle_error(response)

            data = response.json()
            return data.get("data", [])

        except httpx.RequestError as e:
            logger.error(f"Failed to get models: {e}")
            raise APIError(detail=f"Failed to retrieve models: {e}")
