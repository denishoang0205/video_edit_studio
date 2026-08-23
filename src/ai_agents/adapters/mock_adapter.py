import asyncio
import json
import re
from typing import Any, List
from src.ai_agents.domain.interfaces import ILLMProvider, LLMMessage, LLMResponse


class MockLLMAdapter(ILLMProvider):
    """Fallback LLM Adapter generating high-converting TikTok metadata when no API key is provided."""

    async def generate(self, messages: List[LLMMessage], **kwargs: Any) -> LLMResponse:
        await asyncio.sleep(0.05)
        last_prompt = messages[-1].content if messages else ""

        # Extract video title or keyword from prompt
        topic_match = re.search(r"Video/Topic:\s*(.*)", last_prompt)
        topic = topic_match.group(1).strip() if topic_match else "Clip Hot TikTok"

        # Generate intelligent mock JSON response
        simulated_data = {
            "hook_title": f"BÍ MẬT {topic.upper()} MÀ 99% MỌI NGƯỜI CHƯA BIẾT!",
            "alternative_hooks": [
                f"Đừng bỏ lỡ: Sự thật về {topic}!",
                f"Top 3 điều bạn phải biết về {topic}",
                f"Xem ngay trước khi bị xóa: {topic}"
            ],
            "caption": f"Khám phá ngay bí quyết cực đỉnh về {topic} cùng TikTok Studio! Lưu lại xem ngay kẻo quên nhé! 👇🔥",
            "hashtags": [f"#{re.sub(r'[^a-zA-Z0-9]', '', topic).lower()}", "#learnontiktok", "#viralvideo", "#fyp", "#xuhuong"],
            "suggested_ratio": "3:4",
            "suggested_banner_style": "rounded_white",
            "suggested_split_parts": 2
        }

        return LLMResponse(
            content=json.dumps(simulated_data, ensure_ascii=False, indent=2),
            token_usage={"prompt_tokens": 100, "completion_tokens": 80, "total_tokens": 180}
        )
