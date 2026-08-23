import logging
from typing import Any, AsyncGenerator, List, Optional
from src.crewai_core.domain.interfaces.llm import ILLMProvider, LLMMessage, LLMResponse
from src.crewai_core.domain.exceptions import LLMProviderError

logger = logging.getLogger(__name__)


class OpenAILLMAdapter(ILLMProvider):
    """Production Adapter for OpenAI / Azure OpenAI endpoints."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model_name: str = "gpt-4o",
        base_url: Optional[str] = None,
    ):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
            except ImportError:
                raise LLMProviderError("Package 'openai' is required. Install via `pip install openai`.")
        return self._client

    async def generate(self, messages: List[LLMMessage], **kwargs: Any) -> LLMResponse:
        client = self._get_client()
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            response = await client.chat.completions.create(
                model=self.model_name,
                messages=formatted_messages,
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 4096),
            )
            choice = response.choices[0]
            usage = {
                "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                "total_tokens": response.usage.total_tokens if response.usage else 0,
            }
            return LLMResponse(
                content=choice.message.content or "",
                token_usage=usage,
                finish_reason=choice.finish_reason,
            )
        except Exception as e:
            logger.error(f"OpenAI API invocation failed: {str(e)}")
            raise LLMProviderError(f"OpenAI API Error: {str(e)}") from e

    async def generate_stream(self, messages: List[LLMMessage], **kwargs: Any) -> AsyncGenerator[str, None]:
        client = self._get_client()
        formatted_messages = [{"role": m.role, "content": m.content} for m in messages]

        try:
            stream = await client.chat.completions.create(
                model=self.model_name,
                messages=formatted_messages,
                stream=True,
            )
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield chunk.choices[0].delta.content
        except Exception as e:
            logger.error(f"OpenAI Streaming Error: {str(e)}")
            raise LLMProviderError(f"OpenAI Streaming Error: {str(e)}") from e
