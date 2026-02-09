import json
import re
from typing import List, Dict, Any, Optional
from services.ai import ContentService
from services.video_prompts import (
    STORY_REEL_TEMPLATE,
    SHORT_VIDEO_TEMPLATE,
    FACT_IMAGE_TEMPLATE,
    QUIZ_TEMPLATE,
    TEXT_STORY_TEMPLATE,
    CONCEPT_PROMPT_TEMPLATE
)

class VideoAiService:
    @staticmethod
    async def _call_ai(config: Dict[str, Any], prompt: str) -> str:
        """Calls the appropriate AI provider based on config."""
        provider = config.get("provider", "Gemini")
        model = config.get("model", "gemini-2.0-flash")
        api_key = config.get("api_key") or config.get("apiKey")
        base_url = config.get("base_url") or config.get("baseUrl")
        
        print(f"[VideoAI] 🤖 Request to {provider} ({model})")
        # print(f"[VideoAI] 📜 Prompt Preview:\n{prompt[:500]}...")

        if provider == 'Groq':
            return await ContentService.generate_with_groq(api_key, prompt, model, base_url)
        elif provider == 'OpenRouter':
            return await ContentService.generate_with_openrouter(api_key, prompt, model, base_url)
        else:
            return await ContentService.generate_with_gemini(api_key, prompt, model)

    @staticmethod
    def _parse_json(response: str) -> Any:
        try:
            # Extract JSON block if present
            json_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', response)
            json_str = json_match.group(1).strip() if json_match else response.strip()
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[VideoAI] JSON Parse Error: {e}\nResponse: {response}")
            raise Exception("Failed to parse AI response as JSON")

    @staticmethod
    def _interpolate(template: str, variables: Dict[str, Any]) -> str:
        result = template
        for key, value in variables.items():
            result = result.replace(f"{{{{{key}}}}}", str(value))
        return result

    @staticmethod
    async def generate_concept(config: Dict[str, Any], prompt: str) -> str:
        return await VideoAiService._call_ai(config, prompt)

    @staticmethod
    async def generate_story_reel_content(config: Dict[str, Any], topic: str, style: str, system_prompt: str = None) -> Dict[str, str]:
        template = system_prompt or STORY_REEL_TEMPLATE
        prompt = VideoAiService._interpolate(template, {"topic": topic, "style": style})
        response = await VideoAiService._call_ai(config, prompt)
        return VideoAiService._parse_json(response)

    @staticmethod
    async def generate_short_video_content(config: Dict[str, Any], topic: str, system_prompt: str = None) -> Dict[str, List[Dict[str, Any]]]:
        template = system_prompt or SHORT_VIDEO_TEMPLATE
        prompt = VideoAiService._interpolate(template, {"topic": topic})
        response = await VideoAiService._call_ai(config, prompt)
        return VideoAiService._parse_json(response)

    @staticmethod
    async def generate_fact_image_content(config: Dict[str, Any], topic: str, system_prompt: str = None) -> Dict[str, Any]:
        template = system_prompt or FACT_IMAGE_TEMPLATE
        prompt = VideoAiService._interpolate(template, {"topic": topic})
        response = await VideoAiService._call_ai(config, prompt)
        return VideoAiService._parse_json(response)

    @staticmethod
    async def generate_quiz_content(config: Dict[str, Any], topic: str, count: int, system_prompt: str = None) -> Dict[str, List[Dict[str, Any]]]:
        template = system_prompt or QUIZ_TEMPLATE
        prompt = VideoAiService._interpolate(template, {"topic": topic, "count": count})
        response = await VideoAiService._call_ai(config, prompt)
        return VideoAiService._parse_json(response)

    @staticmethod
    async def generate_text_story_content(config: Dict[str, Any], scenario: str, person_a: str, person_b: str, message_count: int, tone: str, system_prompt: str = None) -> Dict[str, Any]:
        template = system_prompt or TEXT_STORY_TEMPLATE
        prompt = VideoAiService._interpolate(template, {
            "scenario": scenario,
            "personA": person_a,
            "personB": person_b,
            "messageCount": message_count,
            "tone": tone
        })
        response = await VideoAiService._call_ai(config, prompt)
        return VideoAiService._parse_json(response)
