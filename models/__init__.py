from typing import Optional, List
from sqlmodel import Field, SQLModel, JSON
from datetime import datetime
from enum import Enum
from pydantic import model_validator
import uuid

# Enums
class JobType(str, Enum):
    RSS_FETCH = 'RSS_FETCH'
    AI_GENERATE = 'AI_GENERATE'
    FB_PUBLISH = 'FB_PUBLISH'
    X_PUBLISH = 'X_PUBLISH'
    YOUTUBE_PUBLISH = 'YOUTUBE_PUBLISH'
    FLOW_EXECUTION = 'FLOW_EXECUTION'
    VIDEO_CHECK_STATUS = 'VIDEO_CHECK_STATUS' 
    DAILYMOTION_UPLOAD = 'DAILYMOTION_UPLOAD'
    VIDEO_RENDER = 'VIDEO_RENDER'

class JobStatus(str, Enum):
    PENDING = 'pending'
    PROCESSING = 'processing'
    SUCCESS = 'success'
    FAILED = 'failed'
    CANCELLED = 'cancelled'
    DELAYED = 'delayed'
    SKIPPED = 'skipped'

class SocialPlatform(str, Enum):
    FACEBOOK = 'FACEBOOK'
    X = 'X'
    INSTAGRAM = 'INSTAGRAM'
    YOUTUBE = 'YOUTUBE'
    DAILYMOTION = 'DAILYMOTION'
    TIKTOK = 'TikTok'

# Models

class Job(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    type: JobType
    payload: dict = Field(default={}, sa_type=JSON) # JSON Column
    status: JobStatus = Field(default=JobStatus.PENDING)
    scheduled_at: datetime
    created_at: datetime = Field(default_factory=datetime.utcnow)
    attempts: int = Field(default=0)
    error: Optional[str] = None
    log_id: Optional[str] = None
    execution_logs: List[str] = Field(default=[], sa_type=JSON)

    # Validator to convert string to datetime (SQLite Fix)
    # Validator to convert string to datetime (SQLite Fix)
    from pydantic import model_validator

    @model_validator(mode='before')
    @classmethod
    def parse_dates(cls, data: any) -> any:
        if isinstance(data, dict):
            for dt_field in ['created_at', 'scheduled_at']:
                if dt_field in data and isinstance(data[dt_field], str):
                    try:
                        data[dt_field] = datetime.fromisoformat(data[dt_field].replace('Z', '+00:00'))
                    except:
                        pass
        return data

class RSSFeed(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    url: str
    auto_fetch: bool = Field(default=False)
    last_fetched_at: Optional[datetime] = None

    @model_validator(mode='before')
    @classmethod
    def parse_dates(cls, data: any) -> any:
        if isinstance(data, dict):
            for dt_field in ['last_fetched_at']:
                if dt_field in data and isinstance(data[dt_field], str):
                    try:
                        data[dt_field] = datetime.fromisoformat(data[dt_field].replace('Z', '+00:00'))
                    except:
                        pass
        return data
class FlowConfig(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    name: str
    source_type: str # RSS, AI_TOPIC, etc.
    is_active: bool = True
    
    # Identity
    target_page_ids: List[str] = Field(default=[], sa_type=JSON)
    ai_config_id: Optional[str] = None
    image_gen_config_id: Optional[str] = None
    
    # Source Configs
    rss_feeds: List[dict] = Field(default=[], sa_type=JSON)
    ai_topic_prompt: Optional[str] = None
    
    # Schedule
    schedule_frequency: str = "Daily" # Daily, Hourly
    posting_time: str = "09:00"
    
    # Metadata
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_run_at: Optional[datetime] = None
    
    # New Parity Fields
    rewrite_policy: str = "AI_REWRITE"
    hashtag_strategy: str = "AUTO"
    post_template: Optional[str] = None
    custom_ai_prompt: Optional[str] = None
    fixed_times: List[str] = Field(default=["09:00"], sa_type=JSON)
    enable_quiet_hours: bool = False
    posting_window_start: str = "09:00"
    posting_window_end: str = "21:00"
    
    # Specialized Configs
    image_caption_config: Optional[dict] = Field(default=None, sa_type=JSON)
    video_automation_config: Optional[dict] = Field(default=None, sa_type=JSON)
    weather_config: Optional[dict] = Field(default=None, sa_type=JSON)
    
    # Missing Parity Fields (Direct Access)
    daily_limit: Optional[int] = None
    content_tone: Optional[str] = None
    max_items_per_refresh: int = Field(default=5)
    min_articles_required: int = Field(default=1)
    posting_order: str = Field(default="NEWEST_FIRST")
    feed_added_timestamp: Optional[float] = None
    fallback_action: str = Field(default="MOVE_TO_REVIEW")

    model_config = {
        "alias_generator": lambda x: "".join([word.capitalize() if i > 0 else word for i, word in enumerate(x.split("_"))]),
        "populate_by_name": True
    }

    @classmethod
    def __pydantic_before_init__(cls, data):
        if isinstance(data, dict):
            for dt_field in ['created_at', 'last_run_at']:
                if dt_field in data and isinstance(data[dt_field], str):
                    try:
                        data[dt_field] = datetime.fromisoformat(data[dt_field].replace('Z', '+00:00'))
                    except:
                        pass
        return data
    
    # Validator to convert string to datetime
    @classmethod
    def __pydantic_before_init__(cls, data):
        if isinstance(data, dict):
            for dt_field in ['created_at', 'last_run_at']:
                if dt_field in data and isinstance(data[dt_field], str):
                    try:
                        data[dt_field] = datetime.fromisoformat(data[dt_field].replace('Z', '+00:00'))
                    except:
                        pass
        return data

class AppSettings(SQLModel, table=True):
    id: int = Field(default=1, primary_key=True) # Singleton row
    
    # Legacy/Simplicity
    gemini_api_key: Optional[str] = None
    fb_page_id: Optional[str] = None
    fb_access_token: Optional[str] = None
    
    # Core Configs (JSON Lists)
    ai_configs: List[dict] = Field(default=[], sa_type=JSON)
    image_gen_configs: List[dict] = Field(default=[], sa_type=JSON)
    social_media_accounts: List[dict] = Field(default=[], sa_type=JSON) # Storing here for 1:1 mirroring
    
    # System
    enable_background_worker: bool = False
    max_posts_per_day: int = 5
    retry_interval_minutes: int = 10
    time_zone: str = "Asia/Dhaka"
    theme: str = "system"
    
    # Automation V3
    enable_automation: bool = False
    enable_notifications: bool = False
    posting_window_start: str = "09:00"
    posting_window_end: str = "18:00"
    auto_generate_from_rss: bool = False
    auto_publish: bool = False
    auto_topics: List[str] = Field(default=[], sa_type=JSON)
    
    # External Services
    nca_api_url: Optional[str] = None
    hf_token: Optional[str] = None
    hf_repo: Optional[str] = None
    
    # Extreme Parity (Immortal Mode)
    dedicated_server_mode: bool = False
    voice_alerts: bool = False

    model_config = {
        "alias_generator": lambda x: "".join([word.capitalize() if i > 0 else word for i, word in enumerate(x.split("_"))]),
        "populate_by_name": True
    }
    
class SocialMediaAccount(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    platform: SocialPlatform
    account_name: str
    handle: str
    access_token: str
    page_id: Optional[str] = None
    refresh_token: Optional[str] = None
    client_id: Optional[str] = None
    client_secret: Optional[str] = None

    model_config = {
        "alias_generator": lambda x: "".join([word.capitalize() if i > 0 else word for i, word in enumerate(x.split("_"))]),
        "populate_by_name": True
    }
    
class GeneratedPost(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    content: str
    image_uri: Optional[str] = None
    original_source: Optional[str] = None
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    status: str = "draft"
    published_at: Optional[datetime] = None
    flow_id: Optional[str] = None

    model_config = {
        "alias_generator": lambda x: "".join([word.capitalize() if i > 0 else word for i, word in enumerate(x.split("_"))]),
        "populate_by_name": True
    }

    @classmethod
    def __pydantic_before_init__(cls, data):
        if isinstance(data, dict):
            for dt_field in ['generated_at', 'published_at']:
                if dt_field in data and isinstance(data[dt_field], str):
                    try:
                        data[dt_field] = datetime.fromisoformat(data[dt_field].replace('Z', '+00:00'))
                    except:
                        pass
        return data

class IdeaHistory(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    flow_id: str
    concept: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    model_config = {
        "alias_generator": lambda x: "".join([word.capitalize() if i > 0 else word for i, word in enumerate(x.split("_"))]),
        "populate_by_name": True
    }

    @classmethod
    def __pydantic_before_init__(cls, data):
        if isinstance(data, dict):
            for dt_field in ['timestamp']:
                if dt_field in data and isinstance(data[dt_field], str):
                    try:
                        data[dt_field] = datetime.fromisoformat(data[dt_field].replace('Z', '+00:00'))
                    except:
                        pass
        return data

class AppNotification(SQLModel, table=True):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), primary_key=True)
    title: str
    body: str
    type: str = Field(default="info") # info, success, error, warning
    read: bool = Field(default=False)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def __pydantic_before_init__(cls, data):
        if isinstance(data, dict):
            for dt_field in ['created_at']:
                if dt_field in data and isinstance(data[dt_field], str):
                    try:
                        data[dt_field] = datetime.fromisoformat(data[dt_field].replace('Z', '+00:00'))
                    except:
                        pass
        return data
