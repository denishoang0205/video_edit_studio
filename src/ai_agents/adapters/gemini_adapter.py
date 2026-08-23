import logging
from typing import Any, List, Optional
from src.ai_agents.domain.interfaces import ILLMProvider, LLMMessage, LLMResponse

logger = logging.getLogger(__name__)


class GeminiLLMAdapter(ILLMProvider):
    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash"):
        self.api_key = api_key
        self.model_name = model_name
        self._client = None

    def _get_client(self):
        if not self._client:
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate(self, messages: List[LLMMessage], **kwargs: Any) -> LLMResponse:
        client = self._get_client()
        full_prompt = "\n".join([f"{m.role.upper()}: {m.content}" for m in messages])
        resp = await client.aio.models.generate_content(
            model=self.model_name,
            contents=full_prompt
        )
        text = resp.text or "{}"
        return LLMResponse(
            content=text,
            token_usage={"prompt_tokens": len(full_prompt) // 4, "completion_tokens": len(text) // 4, "total_tokens": (len(full_prompt) + len(text)) // 4}
        )
