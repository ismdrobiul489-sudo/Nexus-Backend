import httpx
from typing import Optional, List, Dict, Any

# ============================================================
# VALID ENUM LISTS (from NCAKit OpenAPI schema)
# ============================================================
VALID_MUSIC_GENRES = [
    'sad', 'melancholic', 'happy', 'euphoric/high', 'excited', 
    'chill', 'uneasy', 'angry', 'dark', 'hopeful', 
    'contemplative', 'funny/quirky'
]

VALID_VOICES = [
    'af_heart', 'af_alloy', 'af_aoede', 'af_bella', 'af_jessica', 
    'af_kore', 'af_nicole', 'af_nova', 'af_river', 'af_sarah', 
    'af_sky', 'am_adam', 'am_echo', 'am_eric', 'am_fenrir', 
    'am_liam', 'am_michael', 'am_onyx', 'am_puck', 'am_santa',
    'bf_emma', 'bf_isabella', 'bm_george', 'bm_lewis', 
    'bf_alice', 'bf_lily', 'bm_daniel', 'bm_fable'
]

VALID_STYLES = [
    'semi-realistic', 'anime', 'cartoon', 'realistic', 
    'watercolor', 'sticky animation'
]

# ============================================================
# HELPER FUNCTIONS - Safe Defaults with Fallback
# ============================================================
def get_valid_music(choice: Optional[str]) -> Optional[str]:
    """
    Validates music choice against allowed values.
    Returns 'chill' as safe default if invalid.
    Returns None if input is None (no music).
    """
    if choice is None:
        return None
    
    original = choice
    normalized = choice.lower().strip()
    
    # Check direct match
    if normalized in VALID_MUSIC_GENRES:
        return normalized
    
    # Check if any valid genre contains the input (fuzzy match)
    for genre in VALID_MUSIC_GENRES:
        if normalized in genre or genre in normalized:
            print(f"[AUTO-FIX] Music choice '{original}' was remapped to '{genre}'.")
            return genre
    
    # Default fallback to 'chill'
    print(f"[AUTO-FIX] Music choice '{original}' was invalid. Remapped to 'chill'.")
    return 'chill'

def get_valid_voice(choice: Optional[str], default: str = "af_heart") -> str:
    """
    Validates voice choice against allowed values.
    Returns default if invalid.
    """
    if choice is None:
        return default
    
    normalized = choice.lower().strip()
    if normalized in VALID_VOICES:
        return normalized
    
    print(f"[AUTO-FIX] Voice '{choice}' was invalid. Remapped to '{default}'.")
    return default

def get_valid_style(choice: Optional[str], default: str = "semi-realistic") -> str:
    """
    Validates image style against allowed values.
    Returns default if invalid.
    """
    if choice is None:
        return default
    
    normalized = choice.lower().strip()
    if normalized in VALID_STYLES:
        return normalized
    
    print(f"[AUTO-FIX] Style '{choice}' was invalid. Remapped to '{default}'.")
    return default


class NcaKitService:
    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')

    async def _post(self, endpoint: str, data: Dict[str, Any]) -> Dict[str, Any]:
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                response = await client.post(f"{self.base_url}{endpoint}", json=data)
                if not response.is_success:
                    # Log detailed error for debugging
                    error_text = response.text
                    print(f"[NCAKit] ❌ HTTP {response.status_code} at {endpoint}. Response: {error_text[:500]}")
                response.raise_for_status()
                return response.json()
            except httpx.ReadTimeout:
                print(f"[NCAKit] ⏳ POST Timeout at {endpoint}. Server is likely processing.")
                raise


    async def _get(self, endpoint: str, retries: int = 3) -> Any:
        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    response = await client.get(f"{self.base_url}{endpoint}")
                    response.raise_for_status()
                    return response.json()
            except httpx.ReadTimeout:
                if attempt == retries - 1:
                    print(f"[NCAKit] ❌ Permanent GET Timeout at {endpoint} after {retries} attempts.")
                    raise
                print(f"[NCAKit] ⏳ GET Timeout at {endpoint} (Attempt {attempt+1}/{retries}). Retrying...")
                import asyncio
                await asyncio.sleep(2)
            except Exception as e:
                print(f"[NCAKit] ❌ GET Error at {endpoint}: {e}")
                raise

    # --- Health ---
    async def verify_health(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(f"{self.base_url}/health")
                if response.status_code == 200:
                    data = response.json()
                    return data.get("status") in ["healthy", "ok"] or True
                return False
        except Exception:
            return False

    # --- Metadata ---
    async def get_voices(self) -> List[str]:
        return await self._get("/api/voices")

    async def get_music_tags(self) -> List[str]:
        return await self._get("/api/music-tags")

    async def get_styles(self) -> List[str]:
        return await self._get("/api/styles")

    # --- Story Reels ---
    async def create_story_reel(self, script: str, image_style: str = "semi-realistic", voice: str = "af_heart"):
        # Validate inputs before API call
        validated_style = get_valid_style(image_style)
        validated_voice = get_valid_voice(voice)
        
        return await self._post("/api/story/story-reel", {
            "script": script,
            "image_style": validated_style,
            "voice": validated_voice
        })

    # --- Short Video ---
    async def create_short_video(self, scenes: List[Dict], config: Dict):
        # Validate config values before API call
        validated_config = config.copy()
        
        if "music" in validated_config:
            validated_config["music"] = get_valid_music(validated_config["music"])
        if "voice" in validated_config:
            validated_config["voice"] = get_valid_voice(validated_config["voice"])
        
        return await self._post("/api/video/short-video", {
            "scenes": scenes,
            "config": validated_config
        })

    # --- Fact Image ---
    async def create_fact_image(self, model: str, image_prompt: str, fact_text: str, fact_heading: str, duration: int = 5, heading_background: Optional[Dict] = None):
        return await self._post("/api/fact-image/", {
            "model": model,
            "image_prompt": image_prompt,
            "fact_text": fact_text,
            "fact_heading": fact_heading,
            "duration": duration,
            "heading_background": heading_background
        })


    # --- Quiz Reel ---
    async def create_quiz_reel(self, quizzes: List[Dict], voice: str = "af_heart"):
        return await self._post("/api/quiz/generate", {
            "quizzes": quizzes,
            "voice": voice
        })

    # --- Text Story ---
    async def create_text_story(self, messages: List[Dict], person_a_name: str, person_b_name: str, voice_a: str, voice_b: str, ending_text: Optional[str] = None):
        return await self._post("/api/text-story/generate", {
            "messages": messages,
            "person_a_name": person_a_name,
            "person_b_name": person_b_name,
            "voice_a": voice_a,
            "voice_b": voice_b,
            "ending_text": ending_text
        })

    async def ai_generate_conversation(self, prompt: str, message_count: int, tone: str):
        return await self._post("/api/text-story/ai-generate", {
            "prompt": prompt,
            "message_count": message_count,
            "tone": tone
        })

    # --- Trends ---
    async def get_trending_now(self, request: Dict[str, Any]):
        return await self._post("/api/trends/trending-now", request)

    async def keyword_research(self, request: Dict[str, Any]):
        return await self._post("/api/trends/keyword-research", request)

    # --- Status ---
    async def get_status(self, job_id: str, module: str = "story-reel"):
        # Map module to status endpoint path pattern (1:1 Parity with ncakitService.ts)
        path = ""
        m = module.lower()
        if m == "story-reel":
            path = f"/api/story/story-reel/{job_id}/status"
        elif m == "short-video":
            path = f"/api/video/short-video/{job_id}/status"
        elif m == "fact-image":
            path = f"/api/fact-image/{job_id}/status"
        elif m == "quiz":
            path = f"/api/quiz/{job_id}/status"
        elif m == "text-story":
            path = f"/api/text-story/{job_id}/status"
        else:
             path = f"/api/jobs/{job_id}/status"

        return await self._get(path)
