from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

# --- Sync Protocol Schema (DTOs) ---
# This defines the contract between React Native (Master) and Python (node)

class SyncSchedule(BaseModel):
    enabled: bool = True
    cron_expression: Optional[str] = None # "0 9 * * *"
    interval_minutes: Optional[int] = None
    timezone: str = "Asia/Dhaka"
    fixed_times: List[str] = [] # ["09:00", "14:00"] for multi-shot

    model_config = {
        "alias_generator": lambda x: "".join([word.capitalize() if i > 0 else word for i, word in enumerate(x.split("_"))]),
        "populate_by_name": True
    }

class SyncCredentials(BaseModel):
    # Encrypted fields (if strictly secure) or plain (if trusted environment)
    gemini_key: Optional[str] = None
    fb_token: Optional[str] = None
    youtube_token: Optional[str] = None
    model: Optional[str] = None # The selected AI model (e.g. gemini-1.5-flash, llama-3.3-70b-versatile)
    provider: Optional[str] = "Gemini" # Provider Name (Gemini, Groq, OpenRouter)
    base_url: Optional[str] = None # Custom Base URL
    env_vars: Dict[str, str] = {} # For flexible additions
    social_accounts: List[Dict[str, Any]] = [] # Full list of authenticated accounts

    model_config = {
        "alias_generator": lambda x: "".join([word.capitalize() if i > 0 else word for i, word in enumerate(x.split("_"))]),
        "populate_by_name": True
    }

class SyncConfigPayload(BaseModel):
    # Generic payload to support all flow types
    niche: Optional[str] = None
    prompt: Optional[str] = None
    rss_urls: List[str] = []
    
    # Specifics
    video_style: Optional[str] = None
    voice: Optional[str] = None
    
    # Missing explicit fields
    video_automation_config: Optional[Dict[str, Any]] = None
    ai_config_id: Optional[str] = None
    image_gen_config_id: Optional[str] = None
    
    # Raw config dump for parity with TS 'FlowConfig'
    raw_config: Dict[str, Any] = {}

    model_config = {
        "alias_generator": lambda x: "".join([word.capitalize() if i > 0 else word for i, word in enumerate(x.split("_"))]),
        "populate_by_name": True
    }

class SyncAssistant(BaseModel):
    id: str = Field(..., description="UUID from Frontend")
    name: str
    flow_type: str # 'RSS_POST', 'AI_TOPIC', 'VIDEO_AUTO'
    
    schedule: SyncSchedule
    config: SyncConfigPayload
    credentials: Optional[SyncCredentials] = None
    
    # Meta
    updated_at: float # Timestamp

    model_config = {
        "alias_generator": lambda x: "".join([word.capitalize() if i > 0 else word for i, word in enumerate(x.split("_"))]),
        "populate_by_name": True
    }

class SyncRequest(BaseModel):
    client_id: str
    timestamp: float
    assistants: List[SyncAssistant]
    social_accounts: Optional[List[Dict[str, Any]]] = None # Top-level accounts sync
    ai_configs: Optional[List[Dict[str, Any]]] = None # Sync AI Providers
