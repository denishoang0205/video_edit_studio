import json
import logging
import re
from typing import Any, Dict, Optional
from src.ai_agents.domain.agent import AgentEntity
from src.ai_agents.domain.task import TaskEntity
from src.ai_agents.domain.crew import CrewEntity
from src.ai_agents.domain.interfaces import ILLMProvider, LLMMessage
from src.ai_agents.adapters.mock_adapter import MockLLMAdapter

logger = logging.getLogger(__name__)


class TikTokContentCrew:
    """Specialized CrewAI Multi-Agent Team for TikTok Video Optimization."""

    def __init__(self, llm_provider: Optional[ILLMProvider] = None):
        self.llm = llm_provider or MockLLMAdapter()

        # Define 3 Specialized Agents
        self.hook_agent = AgentEntity(
            name="Viral Hook Master",
            role="Top TikTok Viral Content Strategist",
            goal="Create irresistible headline hooks under 60 characters with >85% Click-Through Potential.",
            backstory="Experienced TikTok algorithm engineer who analyzed 10,000+ million-view videos.",
            temperature=0.8,
        )

        self.caption_agent = AgentEntity(
            name="SEO & Caption Specialist",
            role="TikTok Algorithm Optimization Expert",
            goal="Write high-retention descriptions, strong Call-To-Action (CTA), and ranking hashtags.",
            backstory="Expert growth hacker specializing in the For You Page (FYP) recommendation algorithm.",
            temperature=0.6,
        )

        self.director_agent = AgentEntity(
            name="Video Creative Director",
            role="Short-Form Video Visual Director",
            goal="Determine ideal visual framing (Aspect Ratio: 3:4 or 9:16) and Banner Style for highest engagement.",
            backstory="Visual designer with expertise in mobile-first user experience and video banner aesthetics.",
            temperature=0.5,
        )

    async def analyze_and_generate(
        self,
        video_name: str,
        channel_name: Optional[str] = None,
        duration_seconds: Optional[float] = None,
        custom_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Runs the multi-agent pipeline to generate viral metadata for a video."""

        prompt = (
            f"Input Video Details:\n"
            f"- Video/Topic: {video_name}\n"
            f"- Target Channel: {channel_name or 'General'}\n"
            f"- Duration: {duration_seconds or 0} seconds\n"
            f"- Custom Notes: {custom_instructions or 'None'}\n\n"
            f"Generate a strictly valid JSON response with the following keys:\n"
            f"1. hook_title: The main short, punchy viral hook title (<55 chars) in Vietnamese or English matching source.\n"
            f"2. alternative_hooks: A list of 3 alternative viral hook titles.\n"
            f"3. caption: An engaging TikTok caption with emojis and CTA.\n"
            f"4. hashtags: A list of 5-7 trending hashtags.\n"
            f"5. suggested_ratio: '3:4' or '9:16'.\n"
            f"6. suggested_banner_style: 'rounded_white' or 'glassmorphism' or 'dark_solid' or 'pill_badge'.\n"
            f"7. suggested_split_parts: integer number of parts if duration > 120s (e.g. 2 or 3)."
        )

        messages = [
            LLMMessage(
                role="system",
                content=(
                    f"{self.hook_agent.build_system_prompt()}\n\n"
                    f"Collaborating with {self.caption_agent.name} and {self.director_agent.name}.\n"
                    f"CRITICAL: Output ONLY a valid JSON object without any Markdown formatting code fences."
                ),
            ),
            LLMMessage(role="user", content=prompt),
        ]

        try:
            resp = await self.llm.generate(messages, json_mode=True)
            raw = resp.content.strip()

            # Clean markdown fences if any
            raw = re.sub(r"^```json\s*", "", raw, flags=re.MULTILINE)
            raw = re.sub(r"^```\s*", "", raw, flags=re.MULTILINE)
            raw = raw.strip()

            result = json.loads(raw)
            return result
        except Exception as e:
            logger.warning(f"Error parsing LLM response, fallback to mock generator: {str(e)}")
            # Fallback mock
            mock = MockLLMAdapter()
            mock_resp = await mock.generate(messages)
            return json.loads(mock_resp.content)
