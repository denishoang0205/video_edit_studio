import logging
from typing import Any, List, Optional
from src.ai_agents.domain.interfaces import ILLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class OpenAILLMAdapter(ILLMProvider):
    def __init__(self, api_key: str, model_name: str = "gpt-4o"):
        self.api_key = api_key
        self.model_name = model_name
        self._client = None

    def _get_client(self):
        if not self._client:
            from openai import AsyncOpenAI
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def generate(self, messages: List[LLMMessage], **kwargs: Any) -> LLMResponse:
        client = self._get_client()
        formatted = [{"role": m.role, "content": m.content} for m in messages]
        resp = await client.chat.completions.create(
            model=self.model_name,
            messages=formatted,
            temperature=kwargs.get("temperature", 0.7),
            response_format={"type": "json_object"} if kwargs.get("json_mode") else None
        )
        choice = resp.choices[0]
        usage = {
            "prompt_tokens": resp.usage.prompt_tokens if resp.usage else 0,
            "completion_tokens": resp.usage.completion_tokens if resp.usage else 0,
            "total_tokens": resp.usage.total_tokens if resp.usage else 0
        }
        return LLMResponse(content=choice.message.content or "{}", token_usage=usage)
