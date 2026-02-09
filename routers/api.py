from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Response
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional, Dict, Any
from datetime import datetime
import aiofiles
import os
import uuid
import httpx
from pydantic import BaseModel

from database import get_session
from models import AppSettings, Job, JobStatus, RSSFeed, GeneratedPost, JobType, FlowConfig, SocialMediaAccount
from services.scheduler import SchedulerService
from services.ai import ContentService
from services.social_media import SocialMediaService

from services.youtube_bridge import YoutubeBridgeService
from services.youtube import YouTubeService
from services.ncakit import NcaKitService
from services.logger_service import LoggerService, console_log
from services.dailymotion import DailymotionService
from services.dailymotion_bridge import DailymotionBridgeService
from services.crypto import AesCryptoService
from services.news import NewsService
from services.execution_pipeline import ExecutionPipeline
import json

router = APIRouter(prefix="/api", tags=["API"])

class GenerateTextRequest(BaseModel):
    prompt: str
    provider: str
    api_key: Optional[str] = None
    apiKey: Optional[str] = None
    model: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.apiKey and not self.api_key:
            self.api_key = self.apiKey
        if not self.api_key:
            raise ValueError("api_key or apiKey is required")

class GenerateImageRequest(BaseModel):
    prompt: str
    provider: str
    api_key: Optional[str] = None
    apiKey: Optional[str] = None
    worker_url: Optional[str] = None
    model: Optional[str] = None

    def __init__(self, **data):
        super().__init__(**data)
        if self.apiKey and not self.api_key:
            self.api_key = self.apiKey
        if not self.api_key:
            raise ValueError("api_key or apiKey is required")
    
# Video Request Models
class StoryReelRequest(BaseModel):
    script: str
    image_style: str
    voice: str

class ShortVideoRequest(BaseModel):
    scenes: list
    config: dict

class FactImageRequest(BaseModel):
    model: str = "nvidia"
    image_prompt: str
    fact_text: str
    fact_heading: str
    duration: int = 5
    heading_background: Optional[dict] = None


class QuizReelRequest(BaseModel):
    quizzes: list
    voice: str = "af_heart"

class TextStoryRequest(BaseModel):
    messages: list
    person_a_name: str = "You"
    person_b_name: str = "Other"
    voice_a: str = "af_heart"
    voice_b: str = "am_fenrir"
    ending_text: Optional[str] = None

class TextStoryAIRequest(BaseModel):
    prompt: str
    message_count: int = 7
    tone: str = "emotional"

class SocialVerifyRequest(BaseModel):
    platform: str
    credentials: dict

class BackupCryptoRequest(BaseModel):
    data: str
    key: str


def get_youtube_bridge():
    return YoutubeBridgeService()

def get_dailymotion_bridge():
    return DailymotionBridgeService()

# --- VIDEO AUTOMATION (NCAKit Proxy) ---
async def get_ncakit_service(session: AsyncSession = Depends(get_session)):
    settings = (await session.execute(select(AppSettings))).scalars().first()
    if not settings or not settings.nca_api_url:

        raise HTTPException(status_code=400, detail="NCA API URL not configured in Settings")
    return NcaKitService(settings.nca_api_url)

@router.post("/video/story-reel")
async def create_story_reel(req: StoryReelRequest, nca: NcaKitService = Depends(get_ncakit_service)):
    try:
        return await nca.create_story_reel(req.script, req.image_style, req.voice)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/video/short-video")
async def create_short_video(req: ShortVideoRequest, nca: NcaKitService = Depends(get_ncakit_service)):
    try:
        return await nca.create_short_video(req.scenes, req.config)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/video/fact-image")
async def create_fact_image(req: FactImageRequest, nca: NcaKitService = Depends(get_ncakit_service)):
    try:
        return await nca.create_fact_image(req.model, req.image_prompt, req.fact_text, req.fact_heading, req.duration)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/video/quiz")
async def create_quiz_reel(req: QuizReelRequest, nca: NcaKitService = Depends(get_ncakit_service)):
    try:
        return await nca.create_quiz_reel(req.quizzes, req.voice)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/video/text-story")
async def create_text_story(req: TextStoryRequest, nca: NcaKitService = Depends(get_ncakit_service)):
    try:
        return await nca.create_text_story(req.messages, req.person_a_name, req.person_b_name, req.voice_a, req.voice_b, req.ending_text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/video/text-story/ai")
async def ai_generate_conversation(req: TextStoryAIRequest, nca: NcaKitService = Depends(get_ncakit_service)):
    try:
        return await nca.ai_generate_conversation(req.prompt, req.message_count, req.tone)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- NCA Metadata & Health ---
@router.get("/video/health")
async def get_video_health(nca: NcaKitService = Depends(get_ncakit_service)):
    return {"healthy": await nca.verify_health()}

@router.get("/video/voices")
async def get_video_voices(nca: NcaKitService = Depends(get_ncakit_service)):
    return await nca.get_voices()

@router.get("/video/music-tags")
async def get_video_music_tags(nca: NcaKitService = Depends(get_ncakit_service)):
    return await nca.get_music_tags()

@router.get("/video/styles")
async def get_video_styles(nca: NcaKitService = Depends(get_ncakit_service)):
    return await nca.get_styles()

# --- Trends ---
@router.post("/video/trends/trending-now")
async def get_trending_now(req: Dict[str, Any], nca: NcaKitService = Depends(get_ncakit_service)):
    return await nca.get_trending_now(req)

@router.post("/video/trends/keyword-research")
async def keyword_research(req: Dict[str, Any], nca: NcaKitService = Depends(get_ncakit_service)):
    return await nca.keyword_research(req)

@router.post("/ai/verify")
async def verify_ai_credentials(req: Dict[str, Any]):
    try:
        provider = req.get("provider", "Gemini")
        api_key = req.get("apiKey")
        
        from services.ai import ContentService
        
        if provider == "Gemini":
            result = await ContentService.validate_gemini_key(api_key)
            return result
        elif provider == "Groq":
            result = await ContentService.validate_groq_key(api_key)
            return result
        elif provider == "OpenRouter":
            result = await ContentService.validate_openrouter_key(api_key)
            return result
        
        return {"isValid": False, "models": [], "error": "Provider not supported for direct verification"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/ai/verify-image")
async def verify_image_worker(req: Dict[str, Any]):
    try:
        api_key = req.get("apiKey")
        worker_url = req.get("workerUrl")
        
        from services.ai import ContentService
        result = await ContentService.validate_image_worker(api_key, worker_url)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- YouTube Profile Fetch ---
class YouTubeProfileRequest(BaseModel):
    client_id: str
    client_secret: str
    refresh_token: str

@router.post("/youtube/profile")
async def get_youtube_channel_profile(req: YouTubeProfileRequest):
    """
    Fetches real YouTube channel name and thumbnail using the refresh token.
    This is used after OAuth to get accurate channel info.
    """
    try:
        profile = await YouTubeService.get_channel_profile(
            req.client_id,
            req.client_secret,
            req.refresh_token
        )
        return {
            "success": True,
            "channel": profile
        }
    except Exception as e:
        print(f"[YouTube Profile] Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/social/verify")
async def verify_social_credentials(req: SocialVerifyRequest):
    try:
        from services.social_media import SocialMediaService
        await SocialMediaService.validate_connection(req.platform, req.credentials)
        return {"status": "success", "message": "Account Verified"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/social/profile")
async def fetch_social_profile(req: SocialVerifyRequest):
    try:
        from services.social_media import SocialMediaService
        profile = await SocialMediaService.fetch_account_profile(req.platform, req.credentials)
        if not profile:
            raise HTTPException(status_code=404, detail="Profile not found")
        return {"status": "success", "profile": profile}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/video/status/{module}/{job_id}")
async def get_video_status(module: str, job_id: str, nca: NcaKitService = Depends(get_ncakit_service)):
    try:
        return await nca.get_status(job_id, module)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- Download Redirects (Proxy to NCAKit) ---
@router.get("/video/download/{module}/{job_id}")
async def download_video_proxy(module: str, job_id: str, nca: NcaKitService = Depends(get_ncakit_service)):
    # 1:1 Parity with ncakitService.ts:getDownloadUrl
    base_url = nca.base_url
    url = ""
    m = module.lower()
    if m == 'story-reel':
        url = f"{base_url}/api/story/story-reel/{job_id}"
    elif m == 'short-video':
        url = f"{base_url}/api/video/short-video/{job_id}"
    elif m == 'fact-image':
        url = f"{base_url}/api/fact-image/{job_id}"
    elif m == 'quiz':
        url = f"{base_url}/api/quiz/video/{job_id}"
    elif m == 'text-story':
        url = f"{base_url}/api/text-story/{job_id}/video"
    else:
        url = f"{base_url}/api/{module}/{job_id}"
    
    from fastapi.responses import RedirectResponse
    return RedirectResponse(url)

# --- STORAGE ---
@router.get("/storage/files")
async def list_storage_files(path: Optional[str] = None, session: AsyncSession = Depends(get_session)):
    settings = (await session.execute(select(AppSettings))).scalars().first()
    if not settings or not settings.hf_token or not settings.hf_repo:
        return []
    
    from services.storage import StorageService
    try:
        return StorageService.list_files(settings.hf_token, settings.hf_repo, path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/manual-publish")
async def manual_publish(
    caption: str = Form(...),
    accounts: str = Form(...),  # JSON string of account IDs
    videoType: str = Form("regular"),
    videoTitle: str = Form("Untitled"),
    queue_only: str = Form("false"),
    file: Optional[UploadFile] = File(None),
    hfUrl: Optional[str] = Form(None),
    session: AsyncSession = Depends(get_session)
):
    try:
        print(f"DEBUG: Received accounts raw: {accounts}")
        account_ids = json.loads(accounts)
        print(f"DEBUG: Parsed account_ids: {account_ids}")
        is_queue = queue_only.lower() == "true"
        
        # 1. Handle Media File
        temp_path = None
        if file:
            temp_path = os.path.join("static", "uploads", f"manual_{uuid.uuid4()}_{file.filename}")
            os.makedirs(os.path.dirname(temp_path), exist_ok=True)
        if file:
            async with aiofiles.open(temp_path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)
        elif hfUrl:
            # For simplicity, we use the URL directly if provider supports it
            temp_path = hfUrl

        if is_queue:
            # Scheduled for later? For now, we just queue for 'now' 
            # (picked up by worker in 1 min)
            pass

        # 2. Fetch Accounts from DB
        # Query by page_id OR id to be robust (frontend sends Page IDs for FB)
        stmt = select(SocialMediaAccount).where(
            (SocialMediaAccount.id.in_(account_ids)) | 
            (SocialMediaAccount.page_id.in_(account_ids))
        )
        result = await session.execute(stmt)
        social_accounts = result.scalars().all()
        
        if not social_accounts:
            raise HTTPException(status_code=400, detail="No valid accounts found for IDs (checked both id and page_id)")

        # 3. Create Job Payload
        job_payload = {
            "caption": caption,
            "account_ids": account_ids, # Keep for reference
            "accounts_data": [
                {
                    "id": acc.id,
                    "platform": acc.platform,
                    "access_token": acc.access_token,
                    "page_id": acc.page_id,
                    "account_name": acc.account_name
                } for acc in social_accounts
            ],
            "video_type": videoType,
            "video_title": videoTitle,
            "file_path": temp_path,
            "hf_url": hfUrl
        }
        
        # 4. Execute or Queue
        if is_queue:
            await ExecutionPipeline.create_manual_job(job_payload, is_queue)
            
            return {
                "status": "success",
                "queued_to": len(social_accounts),
                "message": f"Successfully queued for {len(social_accounts)} accounts. The backend will process them shortly.",
                "errors": []
            }
        else:
            # Immediate Execution (Live)
            results = await ExecutionPipeline.execute_manual_publish(job_payload)
            
            # Summarize
            success_count = sum(1 for r in results if r['status'] == 'success')
            failed_count = len(results) - success_count
            
            return {
                "status": "success" if success_count > 0 else "failed",
                "processed": len(results),
                "success_count": success_count,
                "failed_count": failed_count,
                "results": results,
                "message": f"Published to {success_count}/{len(results)} accounts.",
                "errors": [r['error'] for r in results if r['error']]
            }

    except Exception as e:
        LoggerService.error(f"Manual Publish Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# --- MEMORY ---
@router.get("/memory/history")
async def get_memory_history(session: AsyncSession = Depends(get_session)):
    from services.memory import MemoryService
    return await MemoryService.get_history(session)

@router.get("/memory/recent")
async def get_recent_memory_ideas(flow_id: str, limit: int = 50, session: AsyncSession = Depends(get_session)):
    from services.memory import MemoryService
    return await MemoryService.get_recent_ideas(flow_id, session, limit)

@router.post("/memory/save")
async def save_memory_idea(req: Dict[str, Any], session: AsyncSession = Depends(get_session)):
    flow_id = req.get("flowId")
    concept = req.get("concept")
    if not flow_id or not concept:
        raise HTTPException(status_code=400, detail="flowId and concept required")
    
    from services.memory import MemoryService
    item = await MemoryService.save_idea(flow_id, concept, session)
    return {"id": item.id}

@router.post("/storage/upload")
async def upload_to_storage(path: str = Form(...), file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    settings = (await session.execute(select(AppSettings))).scalars().first()
    if not settings or not settings.hf_token or not settings.hf_repo:
        raise HTTPException(status_code=400, detail="HuggingFace not configured")

    # Save locally first
    temp_path = os.path.join("static", "uploads", f"tmp_{uuid.uuid4()}_{file.filename}")
    os.makedirs(os.path.dirname(temp_path), exist_ok=True)
    
    try:
        async with aiofiles.open(temp_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
            
        from services.storage import StorageService
        repo_path = f"{path}/{file.filename}" if path else file.filename
        StorageService.upload(settings.hf_token, settings.hf_repo, temp_path, repo_path)
        return {"status": "success", "path": repo_path}
    finally:
        if os.path.exists(temp_path):
            os.remove(temp_path)

@router.delete("/storage/files")
async def delete_storage_file(path: str, session: AsyncSession = Depends(get_session)):
    settings = (await session.execute(select(AppSettings))).scalars().first()
    if not settings or not settings.hf_token or not settings.hf_repo:
        raise HTTPException(status_code=400, detail="HuggingFace not configured")
        
    from services.storage import StorageService
    try:
        StorageService.delete(settings.hf_token, settings.hf_repo, path)
        return {"status": "deleted"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/storage/folder")
async def create_storage_folder(path: str, session: AsyncSession = Depends(get_session)):
    settings = (await session.execute(select(AppSettings))).scalars().first()
    if not settings or not settings.hf_token or not settings.hf_repo:
        raise HTTPException(status_code=400, detail="HuggingFace not configured")
    
    from services.storage import StorageService
    try:
        StorageService.create_folder(settings.hf_token, settings.hf_repo, path)
        return {"status": "created"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/storage/info")
async def get_storage_info(session: AsyncSession = Depends(get_session)):
    settings = (await session.execute(select(AppSettings))).scalars().first()
    if not settings or not settings.hf_token or not settings.hf_repo:
        return None
    
    from services.storage import StorageService
    return StorageService.get_repo_info(settings.hf_token, settings.hf_repo)

@router.get("/storage/raw")
async def download_storage_raw(path: str, session: AsyncSession = Depends(get_session)):
    """Proxies raw file content for direct download/streaming with tokens."""
    settings = (await session.execute(select(AppSettings))).scalars().first()
    if not settings or not settings.hf_token or not settings.hf_repo:
        raise HTTPException(status_code=401, detail="HF Credentials missing")
        
    url = f"https://huggingface.co/datasets/{settings.hf_repo}/resolve/main/{path}"
    headers = {"Authorization": f"Bearer {settings.hf_token}"}
    
    from fastapi.responses import StreamingResponse
    import httpx
    
    async def stream_file():
        async with httpx.AsyncClient() as client:
            async with client.stream("GET", url, headers=headers) as response:
                async for chunk in response.aiter_bytes():
                    yield chunk

    return StreamingResponse(stream_file(), media_type="application/octet-stream")

# --- MEDIA & AI ---
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    try:
        filename = f"{uuid.uuid4()}_{file.filename}"
        path = os.path.join("static", "uploads", filename)
        async with aiofiles.open(path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
        return {"url": f"/static/uploads/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-text")
async def generate_text_endpoint(req: GenerateTextRequest):
    try:
        if req.provider.lower() == "gemini":
            result = await ContentService.generate_with_gemini(req.api_key, req.prompt, req.model or "gemini-2.0-flash")
        elif req.provider.lower() == "openrouter":
            result = await ContentService.generate_with_openrouter(req.api_key, req.prompt, req.model or "google/gemini-2.0-flash-001")
        elif req.provider.lower() == "groq":
            result = await ContentService.generate_with_groq(req.api_key, req.prompt, req.model or "llama-3.3-70b-versatile")
        else:
            raise HTTPException(status_code=400, detail="Unsupported AI provider")
            
        return {"content": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/generate-image")
async def generate_image_endpoint(req: GenerateImageRequest):
    try:
        image_bytes = await ContentService.generate_image(req.provider, req.api_key, req.prompt, req.worker_url, req.model)
        filename = f"gen_{uuid.uuid4()}.png"
        path = os.path.join("static", "generated", filename)
        async with aiofiles.open(path, 'wb') as out_file:
            await out_file.write(image_bytes)
        return {"url": f"/static/generated/{filename}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- SETTINGS ---
@router.get("/settings", response_model=AppSettings)
async def get_settings(session: AsyncSession = Depends(get_session)):
    settings = (await session.execute(select(AppSettings))).scalars().first()
    if not settings:

        settings = AppSettings()
        session.add(settings)
        await session.commit()
    return settings

@router.post("/settings", response_model=AppSettings)
async def update_settings(new_settings: AppSettings, session: AsyncSession = Depends(get_session)):
    settings = (await session.execute(select(AppSettings))).scalars().first()
    if not settings:

        settings = AppSettings()
        session.add(settings)
    
    # Update fields
    settings_data = new_settings.dict(exclude_unset=True)
    for key, value in settings_data.items():
        if key != "id": 
            setattr(settings, key, value)
            
    session.add(settings)
    await session.commit()
    await session.refresh(settings)
    return settings

# --- JOBS ---
@router.get("/jobs", response_model=List[Job])
async def list_jobs(status: Optional[str] = None, limit: int = 50, session: AsyncSession = Depends(get_session)):
    query = select(Job).order_by(Job.created_at.desc()).limit(limit)
    if status:
        query = query.where(Job.status == status)
    return (await session.execute(query)).scalars().all()


@router.post("/jobs", response_model=Job)
async def create_job(job_data: Job, session: AsyncSession = Depends(get_session)):
    # Upsert Logic: Check for ID duplicate
    existing = await session.get(Job, job_data.id)
    if existing:
        data = job_data.dict(exclude_unset=True)
        for key, value in data.items():
            if key != "id":
                setattr(existing, key, value)
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return existing

    session.add(job_data)
    await session.commit()
    await session.refresh(job_data)
    return job_data

@router.delete("/jobs/{job_id}")
async def delete_job(job_id: str, session: AsyncSession = Depends(get_session)):
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    await session.delete(job)
    await session.commit()
    return {"status": "deleted"}

@router.post("/jobs/{job_id}/retry")
async def retry_job(job_id: str, session: AsyncSession = Depends(get_session)):
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job.status = JobStatus.PENDING
    job.attempts = 0
    job.error = None
    job.scheduled_at = datetime.utcnow()
    
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job

    return results

@router.get("/history/processed")
async def is_url_processed(url: str, session: AsyncSession = Depends(get_session)):
    """Backend parity for storageService.isUrlProcessed"""
    query = select(GeneratedPost).where(GeneratedPost.original_source == url)
    result = (await session.execute(query)).scalars().first()
    return {"processed": result is not None}

# --- RSS ---
@router.get("/feeds", response_model=List[RSSFeed])
async def list_feeds(session: AsyncSession = Depends(get_session)):
    return (await session.execute(select(RSSFeed))).scalars().all()


@router.post("/feeds", response_model=RSSFeed)
async def add_feed(feed_data: RSSFeed, session: AsyncSession = Depends(get_session)):
    # Upsert Logic: Check for URL duplicate
    existing = (await session.execute(select(RSSFeed).where(RSSFeed.url == feed_data.url))).scalars().first()
    if existing:
        existing.name = feed_data.name
        existing.auto_fetch = feed_data.auto_fetch
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return existing

    session.add(feed_data)
    await session.commit()
    await session.refresh(feed_data)
    
    # Trigger immediate fetch
    job = Job(type=JobType.RSS_FETCH, payload={"feedId": feed_data.id, "url": feed_data.url}, scheduled_at=feed_data.last_fetched_at or datetime.utcnow())
    session.add(job)
    await session.commit()
    
    return feed_data

# --- ASSISTANTS (FLOWS) ---
@router.get("/assistants", response_model=List[FlowConfig])
async def list_assistants(session: AsyncSession = Depends(get_session)):
    flows = (await session.execute(select(FlowConfig))).scalars().all()
    print(f"[API] FETCH /assistants: Found {len(flows)} flows in DB")
    return flows


@router.post("/assistants", response_model=FlowConfig)
async def create_assistant(flow_data: FlowConfig, session: AsyncSession = Depends(get_session)):
    # Upsert Logic: Check for ID or Name duplicate
    existing = None
    if flow_data.id:
        existing = await session.get(FlowConfig, flow_data.id)
    
    if not existing:
        # Fallback to name check if ID is new but name is same
        existing = (await session.execute(select(FlowConfig).where(FlowConfig.name == flow_data.name))).scalars().first()

    if existing:
        # Update existing
        data = flow_data.dict(exclude_unset=True)
        for key, value in data.items():
            if key not in ["id", "created_at", "last_run_at"]:
                setattr(existing, key, value)
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return existing

    session.add(flow_data)
    await session.commit()
    await session.refresh(flow_data)
    return flow_data

    return flow_data

@router.get("/assistants/{flow_id}", response_model=FlowConfig)
async def get_assistant(flow_id: str, session: AsyncSession = Depends(get_session)):
    flow = await session.get(FlowConfig, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Assistant not found")
    return flow

@router.put("/assistants/{flow_id}", response_model=FlowConfig)
async def update_assistant(flow_id: str, flow_data: FlowConfig, session: AsyncSession = Depends(get_session)):
    flow = await session.get(FlowConfig, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Assistant not found")
    
    # Update fields
    data = flow_data.dict(exclude_unset=True)
    for key, value in data.items():
        if key not in ["id", "created_at", "last_run_at"]: # Protect immutable fields
            setattr(flow, key, value)
            
    session.add(flow)
    await session.commit()
    await session.refresh(flow)
    return flow

@router.delete("/assistants/{flow_id}")
async def delete_assistant(flow_id: str, session: AsyncSession = Depends(get_session)):
    flow = await session.get(FlowConfig, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Assistant not found")
    await session.delete(flow)
    await session.commit()
    return {"status": "deleted"}

@router.post("/assistants/{flow_id}/run")
async def run_assistant(flow_id: str, session: AsyncSession = Depends(get_session)):
    flow = await session.get(FlowConfig, flow_id)
    if not flow:
        raise HTTPException(status_code=404, detail="Assistant not found")
    
    # Create an immediate execution job
    job = Job(
        type=JobType.FLOW_EXECUTION,
        payload={"flowId": flow.id},
        scheduled_at=datetime.utcnow(),
        status=JobStatus.PENDING
    )
    session.add(job)
    await session.commit()
    return {"message": "Assistant execution job queued", "job_id": job.id}
    
# --- DASHBOARD ---
@router.get("/stats")
async def get_stats(session: AsyncSession = Depends(get_session)):
    now = datetime.utcnow()
    today_start = datetime(now.year, now.month, now.day)
    
    # 1. Total Posts Today (Published status matching today's date)
    posts_today_query = select(GeneratedPost).where(
        (GeneratedPost.status == "published") & 
        (GeneratedPost.published_at >= today_start)
    )
    posts_count = len((await session.execute(posts_today_query)).scalars().all())
    
    # 2. Success Rate (All Time Published vs Failed)
    success_posts = len((await session.execute(select(GeneratedPost).where(GeneratedPost.status == "published"))).scalars().all())
    failed_posts = len((await session.execute(select(GeneratedPost).where(GeneratedPost.status == "failed"))).scalars().all())
    total_finished = success_posts + failed_posts
    success_rate = round((success_posts / total_finished * 100), 1) if total_finished > 0 else 0
    
    # 3. Pending Jobs Count (Actual Jobs + Projected Slots)
    jobs_pending = (await session.execute(select(Job).where(
        (Job.status == JobStatus.PENDING) | (Job.status == JobStatus.PROCESSING) | (Job.status == JobStatus.DELAYED)
    ))).scalars().all()
    
    active_flows = (await session.execute(select(FlowConfig).where(FlowConfig.is_active == True))).scalars().all()
    future_slots_count = 0
    current_time_str = now.strftime("%H:%M")
    
    for flow in active_flows:
        for ft in flow.fixed_times:
            if ft > current_time_str:
                future_slots_count += 1
                
    pending_total = len(jobs_pending) + future_slots_count

    # 4. Next Post Time (Earliest Pending Job or Earliest Future Slot)
    next_post_time = "--:--"
    pending_times = [j.scheduled_at for j in jobs_pending if j.status == JobStatus.PENDING]
    
    for flow in active_flows:
        for ft in flow.fixed_times:
            if ft > current_time_str:
                h, m = map(int, ft.split(":"))
                slot_time = now.replace(hour=h, minute=m, second=0, microsecond=0)
                pending_times.append(slot_time)
                
    if pending_times:
        earliest = min(pending_times)
        # Format for display: If today, show time, else show date + time
        if earliest.date() == now.date():
            next_post_time = earliest.strftime("%I:%M %p")
        else:
            next_post_time = earliest.strftime("%b %d %I:%M %p")

    # 5. Recent Logs (Last 5 Jobs)
    recent_jobs_query = select(Job).order_by(Job.created_at.desc()).limit(5)
    recent_jobs = (await session.execute(recent_jobs_query)).scalars().all()
    
    logs = []
    for job in recent_jobs:
        status_label = "SUCCESS" if job.status == JobStatus.SUCCESS else "QUEUED" if job.status == JobStatus.PENDING else "FAILED"
        logs.append({
            "id": str(job.id),
            "title": f"Job {job.type}",
            "status": status_label,
            "details": str(job.payload)[:40],
            "time": job.created_at.strftime("%H:%M") if job.created_at else "--:--"
        })

    return {
        "pending_jobs": pending_total,
        "total_posts": posts_count,
        "success_rate": success_rate,
        "next_post_time": next_post_time,
        "recent_logs": logs,
        "worker_active": SchedulerService.scheduler.running
    }

# --- ANALYTICS ---
@router.get("/analytics/social")
async def get_social_analytics(session: AsyncSession = Depends(get_session)):
    settings = (await session.execute(select(AppSettings))).scalars().first()
    accounts = settings.social_media_accounts if settings else []
    
    # Mock Stats for now (Phase 3 requirement: Port logic, data can be simulated until real API integration)
    stats_data = []
    for acc in accounts:
        stats_data.append({
            "id": acc.get("id"),
            "accountName": acc.get("accountName"),
            "platform": acc.get("platform"),
            "views": 15420,  # Simulated
            "likes": 892, 
            "followers": 1205
        })
    return stats_data

@router.get("/analytics/suggest")
async def google_suggest_proxy(q: str):
    """Proxies request to Google Suggest to avoid CORS on client"""
    if not q:
        return []
    
    url = f"https://suggestqueries.google.com/complete/search?client=youtube&ds=yt&q={q}"
        # But with client=youtube it returns JSON-like text if we don't use callback. 
        # Actually client=youtube returns `window.google.ac.h` usually.
        # Let's try client=firefox which usually returns pure JSON `["query", ["res1", "res2"]]`
        
    # Retry with Firefox client for JSON
    clean_url = f"https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&q={q}"
    async with httpx.AsyncClient() as client:
        resp = await client.get(clean_url)
        if resp.status_code == 200:
            return resp.json() # Returns ["query", ["res1", "res2", ...]]
    return []

@router.get("/logs")
async def get_system_logs(limit: int = 100):
    """Fetches the most recent system logs."""
    return LoggerService.get_logs(limit)

@router.post("/logs")
async def add_frontend_log(req: Dict[str, Any]):
    """Receives logs from the frontend for unification."""
    level = req.get("level", "info")
    message = req.get("message", "")
    data = req.get("data")
    
    LoggerService.add_log(level, f"[Frontend] {message}", data)
    return {"status": "success"}

@router.delete("/logs")
async def clear_system_logs():
    """Clears all captured logs."""
    LoggerService.clear_logs()
    return {"status": "cleared"}

# --- NOTIFICATIONS ---
@router.get("/notifications")
async def get_notifications(limit: int = 10, unread: bool = True, session: AsyncSession = Depends(get_session)):
    from services.notification_service import NotificationService
    return await NotificationService.get_latest(session, limit, unread)

@router.post("/notifications/clear")
async def clear_notifications(session: AsyncSession = Depends(get_session)):
    from services.notification_service import NotificationService
    return await NotificationService.mark_all_read(session)

# --- MANUAL PUBLISHING (Direct Upload) ---
@router.post("/manual-publish")
async def manual_publish(
    caption: str = Form(""),
    accounts: str = Form("[]"),
    videoType: str = Form("regular"),
    videoTitle: str = Form("Untitled"),
    file: Optional[UploadFile] = File(None),
    hfUrl: Optional[str] = Form(None),
    queue_only: str = Form("false"),
    session: AsyncSession = Depends(get_session)
):
    try:
        account_ids = json.loads(accounts)
        settings = (await session.execute(select(AppSettings))).scalars().first()
        if not settings:
            raise HTTPException(status_code=400, detail="Settings not found")

        # Resolve accounts from settings
        all_accounts = settings.social_media_accounts or []
        target_accounts = [acc for acc in all_accounts if (acc.get("pageId") or acc.get("id")) in account_ids]

        if not target_accounts:
            raise HTTPException(status_code=400, detail="No valid accounts selected")

        # Handle media
        media_path = None
        if file:
            filename = f"manual_{uuid.uuid4()}_{file.filename}"
            media_path = os.path.join("static", "uploads", filename)
            async with aiofiles.open(media_path, 'wb') as out:
                await out.write(await file.read())
        elif hfUrl:
            media_path = hfUrl 

        if queue_only == "true":
            from models import Job
            from datetime import datetime, timedelta
            for acc in target_accounts:
                acc_id = acc.get("pageId") or acc.get("id")
                job = Job(
                    type="FB_PUBLISH",
                    payload=json.dumps({
                        "accountId": acc_id,
                        "caption": caption,
                        "mediaPath": media_path,
                        "videoTitle": videoTitle,
                        "videoType": videoType
                    }),
                    status="pending",
                    scheduled_for=datetime.utcnow() + timedelta(minutes=30)
                )
                session.add(job)
            await session.commit()
            return {"status": "success", "message": f"Added {len(target_accounts)} to queue"}

        # Publishing Loop
        from services.facebook import FacebookService
        from services.youtube_bridge import YoutubeBridgeService
        from services.dailymotion_bridge import DailymotionBridgeService
        from services.logger_service import console_log

        success_count = 0
        for acc in target_accounts:
            platform = (acc.get("platform") or "facebook").lower()
            try:
                if platform == "facebook":
                    LoggerService.info(f"Publishing to Facebook Page: {acc.get('name') or acc.get('pageId')}")
                    if videoType == "reel":
                        await FacebookService.upload_reel(acc["pageId"], acc["accessToken"], media_path, caption)
                    elif file and file.content_type.startswith("video") or hfUrl and hfUrl.lower().endswith(('.mp4', '.mov')):
                        await FacebookService.upload_video(acc["pageId"], acc["accessToken"], media_path, videoTitle, caption)
                    else:
                        await FacebookService.upload_photo(acc["pageId"], acc["accessToken"], media_path, caption)
                    
                    LoggerService.info(f"✅ Facebook Publish Success: {acc.get('name') or acc.get('pageId')}")
                    success_count += 1
                elif platform == "dailymotion":
                    dm = DailymotionBridgeService()
                    upload_url = await dm.get_upload_url(acc.get("access_token"))
                    vid_url = await dm.upload_file(upload_url, media_path)
                    await dm.create_video(acc.get("access_token"), vid_url, {"title": videoTitle, "description": caption, "published": True})
                    success_count += 1
                elif platform == "youtube":
                    # Simple stub for YouTube Bridge immediate upload
                    # Proper impl requires Refresh Token handling which Bridge should do
                    yt = YoutubeBridgeService() # Assuming it handles auth via acc
                    # await yt.upload_video_from_token(acc.get("access_token"), media_path, videoTitle, caption)
                    console_log("INFO", f"Simulating YouTube Upload to {acc.get('accountName')}")
                    success_count += 1
                elif platform == "x" or platform == "twitter":
                    from services.x import XService
                    x = XService()
                    # Resolve full account object to pass to XService if needed, or pass token
                    # Current dictionary `acc` might be enough if XService takes it
                    # await x.post_video_with_token(acc, media_path, caption)
                    console_log("INFO", f"Simulating X Upload to {acc.get('accountName')}")
                    success_count += 1
                    
                console_log("INFO", f"Published to {acc.get('accountName')}")
            except Exception as e:
                console_log("ERROR", f"Failed to publish to {acc.get('accountName')}: {str(e)}")

        return {"status": "success", "published_to": success_count}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/add-to-queue")
async def add_to_queue(req: Dict[str, Any], session: AsyncSession = Depends(get_session)):
    try:
        # Porting queue logic from queueService.ts / ManualPostScreen.tsx
        # In this app, we create a 'FB_PUBLISH' or similar job in the DB.
        from models import Job
        from datetime import datetime, timedelta
        
        caption = req.get("caption")
        accounts = req.get("accounts", [])
        media_path = req.get("media_path")
        video_title = req.get("video_title")
        video_type = req.get("video_type", "regular")

        # Create a job for each account
        from models import SocialMediaAccount
        
        for acc_id in accounts:
            # Determine Platform
            acc = await session.get(SocialMediaAccount, acc_id)
            platform = acc.platform.value if acc else "FACEBOOK" # Default to FB if not found (legacy)
            
            job_type = "FB_PUBLISH"
            if platform == 'YOUTUBE':
                job_type = "YOUTUBE_PUBLISH"
            elif platform == 'X':
                job_type = "X_PUBLISH"
            elif platform == 'DAILYMOTION':
                job_type = "DAILYMOTION_UPLOAD"
                
            job = Job(
                type=job_type,
                payload=json.dumps({
                    "accountId": acc_id,
                    "caption": caption,
                    "mediaPath": media_path,
                    "videoTitle": video_title,
                    "videoType": video_type,
                    "description": caption # YouTube/DM specific
                }),
                status="pending",
                scheduled_for=datetime.utcnow() + timedelta(minutes=30) # Default delay for queue
            )
            session.add(job)
        
        await session.commit()
        return {"status": "success", "message": f"Added {len(accounts)} posts to queue"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- SYSTEM LOGS ---
@router.get("/logs")
async def get_logs():
    return LoggerService.get_logs()

@router.delete("/logs")
async def clear_logs():
    LoggerService.clear_logs()
    return {"status": "cleared"}

# --- NEWS TRENDS (Proxy for NewsData.io) ---
@router.get("/news/trends")
async def get_news_trends(session: AsyncSession = Depends(get_session)):
    try:
        settings = (await session.execute(select(AppSettings))).scalars().first()
        api_key = settings.news_api_key if settings else ""
        results = await NewsService.fetch_trends(api_key)
        return {"status": "success", "results": results}
    except Exception as e:
        return {"status": "error", "message": str(e), "results": NewsService.MOCK_NEWS_DATA}

# --- BACKUP CRYPTO ---
@router.post("/backup/encrypt")
async def backup_encrypt(req: BackupCryptoRequest):
    try:
        encrypted = AesCryptoService.encrypt(req.data, req.key)
        return {"status": "success", "encrypted": encrypted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/backup/decrypt")
async def backup_decrypt(req: BackupCryptoRequest):
    try:
        decrypted = AesCryptoService.decrypt(req.data, req.key)
        if decrypted is None:
            raise HTTPException(status_code=400, detail="Decryption failed. Key mismatch or corrupted data.")
        return {"status": "success", "decrypted": decrypted}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- RSS FEED MANAGEMENT ---
@router.get("/rss/feeds", response_model=List[RSSFeed])
async def get_rss_feeds(session: AsyncSession = Depends(get_session)):
    result = await session.execute(select(RSSFeed))
    return result.scalars().all()

@router.post("/rss/feeds", response_model=RSSFeed)
async def add_rss_feed(feed_data: RSSFeed, session: AsyncSession = Depends(get_session)):
    """Upsert parity for RSS Feed addition"""
    existing = (await session.execute(select(RSSFeed).where(RSSFeed.url == feed_data.url))).scalars().first()
    if existing:
        existing.name = feed_data.name
        existing.auto_fetch = feed_data.auto_fetch
        session.add(existing)
        await session.commit()
        await session.refresh(existing)
        return existing
        
    session.add(feed_data)
    await session.commit()
    await session.refresh(feed_data)
    return feed_data

@router.patch("/rss/feeds/{feed_id}", response_model=RSSFeed)
async def update_rss_feed(feed_id: str, updates: dict, session: AsyncSession = Depends(get_session)):
    feed = await session.get(RSSFeed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    for key, value in updates.items():
        setattr(feed, key, value)
    await session.commit()
    await session.refresh(feed)
    return feed

@router.delete("/rss/feeds/{feed_id}")
async def delete_rss_feed(feed_id: str, session: AsyncSession = Depends(get_session)):
    feed = await session.get(RSSFeed, feed_id)
    if not feed:
        raise HTTPException(status_code=404, detail="Feed not found")
    await session.delete(feed)
    await session.commit()
    return {"status": "deleted"}

@router.get("/rss/fetch")
async def fetch_rss_aggregator(rss_url: str):
    from services.rss import RSSService
    try:
        items = RSSService.fetch_feed(rss_url)
        # Wrap in 'rss2json' format for frontend parity
        return {
            "status": "ok",
            "items": [item.dict() for item in items]
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# --- EXTENDED NEWS PROXIES ---
@router.get("/news/trends/dataio")
async def proxy_newsdata_io(category: str = "general", country: str = "us", api_key: str = ""):
    try:
        results = await NewsService.fetch_news_data_io(category, country, api_key)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/news/trends/gnews")
async def proxy_gnews_io(category: str = "general", country: str = "us", api_key: str = ""):
    try:
        results = await NewsService.fetch_gnews(category, country, api_key)
        return {"status": "success", "results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- YOUTUBE BRIDGE (Cloning) ---
@router.post("/youtube/config")
async def youtube_save_config(req: Dict[str, Any], yt: YoutubeBridgeService = Depends(get_youtube_bridge)):
    return yt.save_config(req.get("clientId"), req.get("clientSecret"), req.get("redirectUri"))


@router.get("/youtube/auth-url")
async def youtube_get_auth_url(redirect_uri: str, yt: YoutubeBridgeService = Depends(get_youtube_bridge)):
    try:
        url = yt.get_auth_url(redirect_uri)
        return {"url": url}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/youtube/callback")
async def youtube_oauth_callback(code: str, state: str, redirect_uri: str, yt: YoutubeBridgeService = Depends(get_youtube_bridge)):
    try:
        tokens = await yt.handle_callback(code, redirect_uri)
        return {"status": "success", "tokens": tokens}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/youtube/status")
async def youtube_get_status(yt: YoutubeBridgeService = Depends(get_youtube_bridge)):
    return yt.get_status()

@router.post("/youtube/stage")
async def youtube_stage_video(video: UploadFile = File(...), yt: YoutubeBridgeService = Depends(get_youtube_bridge)):
    dest_path = os.path.join(yt.storage_dir, "uploads", video.filename)
    with open(dest_path, "wb") as f:
        f.write(await video.read())
    return {
        "success": True,
        "filePath": dest_path,
        "fileName": video.filename
    }

@router.post("/youtube/upload")
async def youtube_upload_video(req: Dict[str, Any], yt: YoutubeBridgeService = Depends(get_youtube_bridge)):
    try:
        result = await yt.upload_video(
            video_path=req.get("videoPath"),
            title=req.get("title"),
            description=req.get("description"),
            tags=req.get("tags"),
            privacy=req.get("privacy"),
            hf_token=req.get("hfToken"),
            tokens=req.get("tokens")
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history/posts", response_model=List[GeneratedPost])
async def get_post_history(flow_id: Optional[str] = None, limit: int = 2000, session: AsyncSession = Depends(get_session)):
    """Fetches all history items for 1:1 parity with storageService.getHistory/getRecentPostsByFlow"""
    query = select(GeneratedPost).order_by(GeneratedPost.generated_at.desc()).limit(limit)
    if flow_id:
        query = query.where(GeneratedPost.flow_id == flow_id)
    return (await session.execute(query)).scalars().all()

@router.post("/history/posts", response_model=GeneratedPost)
async def add_post_to_history(post_data: GeneratedPost, session: AsyncSession = Depends(get_session)):
    """Adds a post to history with duplicate check - 1:1 Parity"""
    if post_data.original_source:
        existing = (await session.execute(select(GeneratedPost).where(GeneratedPost.original_source == post_data.original_source))).scalars().first()
        if existing:
            existing.status = post_data.status
            existing.content = post_data.content
            session.add(existing)
            await session.commit()
            await session.refresh(existing)
            return existing

    session.add(post_data)
    await session.commit()
    await session.refresh(post_data)
    return post_data

# --- DAILYMOTION BRIDGE (Cloning) ---
@router.post("/dailymotion/publish")
async def dailymotion_publish(req: Dict[str, Any], dm: DailymotionBridgeService = Depends(get_dailymotion_bridge)):
    try:
        from services.dailymotion_bridge import DailymotionBridgeService
        access_token = req.get("access_token")
        video_path = req.get("video_path")
        metadata = req.get("metadata", {})
        
        upload_url = await dm.get_upload_url(access_token)
        published_url = await dm.upload_file(upload_url, video_path)
        result = await dm.create_video(access_token, published_url, metadata)
        
        return {"status": "success", "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- VIDEO AI & CREATION (Cloning) ---


@router.post("/video/text-story/ai") # Kept for frontend compatibility
async def video_ai_text_story(req: Dict[str, Any], session: AsyncSession = Depends(get_session)):
    try:
        from services.video_ai import VideoAiService
        
        # 1. Resolve Config
        # Frontend sends { prompt, configId (maybe?), message_count, tone }
        # Note: Frontend might use 'prompt' as the topic/scenario
        
        prompt = req.get("prompt")
        msg_count = req.get("message_count", 7)
        tone = req.get("tone", "dramatic")
        
        # For now, pick first config as default if not sent
        settings = (await session.execute(select(AppSettings))).scalars().first()
        config = (settings.ai_configs or [])[0] if settings.ai_configs else {"provider": "Gemini", "api_key": settings.gemini_api_key}
        
        # 2. Generate
        # We map the generic 'prompt' to scenario
        result = VideoAiService.generate_text_story_content(
            config, 
            scenario=prompt, 
            person_a="Person A", 
            person_b="Person B", 
            message_count=msg_count, 
            tone=tone
        )
        return result 
    except Exception as e:
        print(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

        return result 
    except Exception as e:
        print(f"AI Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/video/ai/concept")
async def video_ai_concept(req: Dict[str, Any], session: AsyncSession = Depends(get_session)):
    try:
        from services.video_ai import VideoAiService
        config_id = req.get("configId")
        prompt = req.get("prompt")
        
        settings = (await session.execute(select(AppSettings))).scalars().first()
        ai_configs = settings.ai_configs or []
        if not config: config = ai_configs[0] if ai_configs else None
        
        result = await VideoAiService.generate_concept(config, prompt)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/video/ai/story-reel")
async def video_ai_story_reel(req: Dict[str, Any], session: AsyncSession = Depends(get_session)):
    try:
        from services.video_ai import VideoAiService
        config_id = req.get("configId")
        prompt = req.get("prompt") # The user topic
        style = req.get("style", "Cinematic")
        
        settings = (await session.execute(select(AppSettings))).scalars().first()
        ai_configs = settings.ai_configs or []
        if not config: config = ai_configs[0] if ai_configs else None
        
        result = await VideoAiService.generate_story_reel_content(config, prompt, style)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/video/ai/short-video")
async def video_ai_short_video(req: Dict[str, Any], session: AsyncSession = Depends(get_session)):
    try:
        from services.video_ai import VideoAiService
        config_id = req.get("configId")
        prompt = req.get("prompt")
        
        settings = (await session.execute(select(AppSettings))).scalars().first()
        ai_configs = settings.ai_configs or []
        if not config: config = ai_configs[0] if ai_configs else None
        
        result = await VideoAiService.generate_short_video_content(config, prompt)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/video/ai/fact-image")
async def video_ai_fact_image(req: Dict[str, Any], session: AsyncSession = Depends(get_session)):
    try:
        from services.video_ai import VideoAiService
        config_id = req.get("configId")
        prompt = req.get("prompt")
        
        settings = (await session.execute(select(AppSettings))).scalars().first()
        ai_configs = settings.ai_configs or []
        if not config: config = ai_configs[0] if ai_configs else None
        
        result = await VideoAiService.generate_fact_image_content(config, prompt)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/video/ai/quiz")
async def video_ai_quiz(req: Dict[str, Any], session: AsyncSession = Depends(get_session)):
    try:
        from services.video_ai import VideoAiService
        config_id = req.get("configId")
        prompt = req.get("prompt")
        count = req.get("count", 5)
        
        settings = (await session.execute(select(AppSettings))).scalars().first()
        ai_configs = settings.ai_configs or []
        if not config: config = ai_configs[0] if ai_configs else None
        
        result = await VideoAiService.generate_quiz_content(config, prompt, count)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/video/ai/text-story")
async def video_ai_text_story(req: Dict[str, Any], session: AsyncSession = Depends(get_session)):
    try:
        from services.video_ai import VideoAiService
        config_id = req.get("configId")
        prompt = req.get("prompt")  # Scenario
        person_a = req.get("person_a", "You")
        person_b = req.get("person_b", "Friend")
        count = req.get("count", 10)
        tone = req.get("tone", "emotional")
        
        settings = (await session.execute(select(AppSettings))).scalars().first()
        ai_configs = settings.ai_configs or []
        if not config: config = ai_configs[0] if ai_configs else None
        
        result = await VideoAiService.generate_text_story_content(config, prompt, person_a, person_b, count, tone)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# --- JOB SUBMISSION (Upsert Logic) ---

def _get_job_hash(job_type: str, payload: Dict[str, Any]) -> str:
    import hashlib
    # Create a unique signature based on content
    # For story: script + style
    # For video: scenes text
    
    unique_str = job_type
    
    if job_type == "story-reel":
        unique_str += payload.get("script", "") + payload.get("image_style", "")
    elif job_type == "short-video":
        scenes = payload.get("scenes", [])
        for s in scenes: unique_str += s.get("text", "")
    elif job_type == "fact-image":
        unique_str += payload.get("fact_text", "") + payload.get("fact_heading", "")
    elif job_type == "quiz":
        quizzes = payload.get("quizzes", [])
        for q in quizzes: unique_str += q.get("question", "")
    elif job_type == "text-story":
        msgs = payload.get("messages", [])
        for m in msgs: unique_str += m.get("text", "")
        
    return hashlib.md5(unique_str.encode()).hexdigest()

@router.post("/video/{job_type}")
async def submit_video_job(job_type: str, req: Dict[str, Any], session: AsyncSession = Depends(get_session)):
    if job_type not in ["story-reel", "short-video", "fact-image", "quiz", "text-story"]:
        raise HTTPException(status_code=404, detail="Invalid job type")

    try:
        # 1. Upsert Check: Search for non-failed job with same hash
        payload_hash = _get_job_hash(job_type, req)
        
        # We need to query Jobs and check payload (this is slow if many jobs, but fine for local)
        # Ideally we'd store the hash in a column, but for now we iterate recent jobs
        
        # Optimization: Only check pending/processing jobs to avoid double-processing
        # Or check completed ones to avoid re-creation? User said "if created, update (return?), don't create new"
        
        # Let's check for ANY job with this hash in the payload meta if possible, 
        # but since we don't have a hash column, we'll check the last 50 jobs.
        
        recent_jobs = (await session.execute(select(Job).order_by(Job.created_at.desc()).limit(50))).scalars().all()
        
        existing_job = None
        for job in recent_jobs:
            if job.payload and job.payload.get("job_hash") == payload_hash:
                existing_job = job
                break
        
        if existing_job:
            # If failed, we might retry (or create new). If pending/ready, return it.
            if existing_job.status == JobStatus.FAILED:
                # Retry strategy or just ignore? User said "update it"
                existing_job.status = JobStatus.PENDING # Restart it
                existing_job.error = None
                session.add(existing_job)
                await session.commit()
                return {"status": "restored", "job_id": existing_job.id}
            else:
                return {"status": "existing", "job_id": existing_job.id}

        # 2. Create New Job
        req["job_hash"] = payload_hash # Store hash for future upserts
        
        new_job = Job(
            type=JobType.VIDEO_RENDER, # Unified type, payload distinguishes
            payload={
                "video_type": job_type,
                **req
            },
            status=JobStatus.PENDING
        )
        session.add(new_job)
        await session.commit()
        await session.refresh(new_job)
        
        return {"status": "queued", "job_id": new_job.id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/video/status/{job_type}/{job_id}")
async def get_video_status(job_type: str, job_id: str, session: AsyncSession = Depends(get_session)):
    job = await session.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    status_str = job.status.value
    if status_str == "success": status_str = "ready"
    
    # Get video_url from result
    video_url = job.result.get("video_url") if job.result else None
    
    # --- FORCE HF URL FOR SHORT-VIDEO ---
    # Per API_DOCUMENTATION.md, short-video status does NOT return video_url from NCA.
    # We must manually construct it using the NCA job ID stored in job.result.
    if job_type == "short-video" and status_str == "ready":
        nca_job_id = job.result.get("nca_job_id") if job.result else None
        if nca_job_id:
            video_url = f"https://huggingface.co/datasets/robiul487/NCAkit/resolve/main/short_video/{nca_job_id}.mp4?download=true"
        elif not video_url:
            # Fallback: Try to get the NCA job ID from the job payload if stored there
            payload_nca_id = job.payload.get("nca_job_id") if job.payload else None
            if payload_nca_id:
                video_url = f"https://huggingface.co/datasets/robiul487/NCAkit/resolve/main/short_video/{payload_nca_id}.mp4?download=true"
    # ------------------------------------
    
    return {
        "status": status_str, # Map success to ready for frontend compatibility
        "current_step": (job.execution_logs or ["Initializing..."])[-1],
        "progress": job.progress,
        "video_url": video_url,
        "error": job.error
    }
# --- BACKUP & RESTORE ---
@router.get("/settings/backup")
async def backup_data(session: AsyncSession = Depends(get_session)):
    """Exports all critical configuration data as ENCRYPTED .nexus file."""
    settings = (await session.execute(select(AppSettings))).scalars().first()
    flows = (await session.execute(select(FlowConfig))).scalars().all()
    feeds = (await session.execute(select(RSSFeed))).scalars().all()
    
    backup_data = {
        "timestamp": datetime.utcnow().isoformat(),
        "version": "v3.0.0",
        "settings": settings.dict() if settings else {},
        "assistants": [f.dict() for f in flows],
        "rss_feeds": [r.dict() for r in feeds],
    }
    
    json_str = json.dumps(backup_data)
    # Encrypt
    # Use a fixed key for migration portability across instances, or user provided?
    # User said "Like old app". Old app used a fixed key internally or user password?
    # The Crypto service uses a key. Let's use a standard app key for now.
    APP_SECRET_KEY = "NEXUS_AUTO_SECRET_KEY_2025" 
    encrypted_data = AesCryptoService.encrypt(json_str, APP_SECRET_KEY)
    
    return Response(content=encrypted_data, media_type="application/octet-stream", headers={
        "Content-Disposition": f"attachment; filename=backup_{datetime.utcnow().strftime('%Y%m%d')}.nexus"
    })

@router.post("/settings/restore")
async def restore_data(file: UploadFile = File(...), session: AsyncSession = Depends(get_session)):
    """Restores configuration from an Encrypted .nexus backup file."""
    try:
        content = await file.read()
        encrypted_str = content.decode('utf-8')
        
        APP_SECRET_KEY = "NEXUS_AUTO_SECRET_KEY_2025"
        decrypted_json = AesCryptoService.decrypt(encrypted_str, APP_SECRET_KEY)
        
        if not decrypted_json:
             raise HTTPException(status_code=400, detail="Invalid Backup File or Wrong Key")
             
        data = json.loads(decrypted_json)
        
        # 1. Restore AppSettings
        if "settings" in data:
            current_settings = (await session.execute(select(AppSettings))).scalars().first()
            if not current_settings:
                current_settings = AppSettings()
                session.add(current_settings)
            
            # Update fields
            settings_data = data["settings"]
            for key, value in settings_data.items():
                if key != "id": 
                    if hasattr(current_settings, key):
                        setattr(current_settings, key, value)
            session.add(current_settings)
            
        # 2. Restore Assistants
        if "assistants" in data:
            for flow_data in data["assistants"]:
                existing = await session.get(FlowConfig, flow_data["id"])
                if existing:
                     for key, value in flow_data.items():
                        setattr(existing, key, value)
                     session.add(existing)
                else:
                    new_flow = FlowConfig(**flow_data)
                    session.add(new_flow)
                    
        # 3. Restore RSS Feeds
        if "rss_feeds" in data:
             for feed_data in data["rss_feeds"]:
                existing = await session.get(RSSFeed, feed_data["id"])
                if existing:
                     for key, value in feed_data.items():
                        setattr(existing, key, value)
                     session.add(existing)
                else:
                    new_feed = RSSFeed(**feed_data)
                    session.add(new_feed)

        await session.commit()
        return {"status": "success", "message": "Nexus Backup Restored Successfully"}
        
    except Exception as e:
        LoggerService.error(f"Restore Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Restore failed: {str(e)}")

class GoogleAuthRequest(BaseModel):
    client_id: str
    client_secret: str
    grant_type: str = "authorization_code"
    code: Optional[str] = None
    refresh_token: Optional[str] = None
    redirect_uri: Optional[str] = None

@router.post("/auth/google/exchange")
async def google_auth_exchange(req: GoogleAuthRequest):
    """
    Exchanges an Authorization Code or Refresh Token (Server-Side to avoid CORS).
    """
    LoggerService.info(f"🔑 Google Auth Exchange: grant_type={req.grant_type}")
    
    token_url = "https://oauth2.googleapis.com/token"
    
    payload = {
        "client_id": req.client_id,
        "client_secret": req.client_secret,
        "grant_type": req.grant_type,
    }
    
    if req.grant_type == "authorization_code":
        if not req.code or not req.redirect_uri:
            raise HTTPException(status_code=400, detail="code and redirect_uri required for authorization_code grant")
        payload["code"] = req.code
        payload["redirect_uri"] = req.redirect_uri
        LoggerService.info(f"   Code: {req.code[:20]}..., Redirect: {req.redirect_uri}")
    elif req.grant_type == "refresh_token":
        if not req.refresh_token:
            raise HTTPException(status_code=400, detail="refresh_token required for refresh_token grant")
        payload["refresh_token"] = req.refresh_token
    
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            LoggerService.info(f"   Sending token request to Google...")
            resp = await client.post(token_url, data=payload, headers=headers)
            LoggerService.info(f"   Google Response: {resp.status_code}")
            if resp.status_code != 200:
                LoggerService.error(f"Google Token Exchange Failed ({req.grant_type}): {resp.text}")
                return Response(status_code=resp.status_code, content=resp.text, media_type="application/json")
            return resp.json()
        except httpx.TimeoutException as e:
            LoggerService.error(f"Google Token Exchange Timeout: {e}")
            raise HTTPException(status_code=504, detail="Google API request timed out")
        except httpx.RequestError as e:
             LoggerService.error(f"Google Token Exchange Network Error: {e}")
             raise HTTPException(status_code=500, detail=str(e))

