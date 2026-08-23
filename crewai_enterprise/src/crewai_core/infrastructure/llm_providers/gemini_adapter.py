import logging
from typing import Any, AsyncGenerator, List, Optional
from src.crewai_core.domain.interfaces.llm import ILLMProvider, LLMMessage, LLMResponse
from src.crewai_core.domain.exceptions import LLMProviderError

logger = logging.getLogger(__name__)


class GeminiLLMAdapter(ILLMProvider):
    """Production Adapter for Google Gemini Model family."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gemini-2.5-flash",
    ):
        self.model_name = model_name
        self.api_key = api_key
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from google import genai
                self._client = genai.Client(api_key=self.api_key)
            except ImportError:
                raise LLMProviderError("Package 'google-genai' is required. Install via `pip install google-genai`.")
        return self._client

    async def generate(self, messages: List[LLMMessage], **kwargs: Any) -> LLMResponse:
        client = self._get_client()
        # Combine messages into Gemini prompt format
        full_prompt = "\n".join([f"{m.role.upper()}: {m.content}" for m in messages])

        try:
            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=full_prompt,
            )
            text_content = response.text or ""
            return LLMResponse(
                content=text_content,
                token_usage={"prompt_tokens": len(full_prompt) // 4, "completion_tokens": len(text_content) // 4, "total_tokens": (len(full_prompt) + len(text_content)) // 4},
                finish_reason="stop",
            )
        except Exception as e:
            logger.error(f"Gemini API invocation failed: {str(e)}")
            raise LLMProviderError(f"Gemini API Error: {str(e)}") from e

    async def generate_stream(self, messages: List[LLMMessage], **kwargs: Any) -> AsyncGenerator[str, None]:
        client = self._get_client()
        full_prompt = "\n".join([f"{m.role.upper()}: {m.content}" for m in messages])
        try:
            response = await client.aio.models.generate_content_stream(
                model=self.model_name,
                contents=full_prompt,
            )
            async for chunk in response:
                if chunk.text:
                    yield chunk.text
        except Exception as e:
            logger.error(f"Gemini Streaming Error: {str(e)}")
            raise LLMProviderError(f"Gemini Streaming Error: {str(e)}") from e
