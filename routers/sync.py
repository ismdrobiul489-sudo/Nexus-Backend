from fastapi import APIRouter, HTTPException, Depends
from sqlmodel import select
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session
from models import SocialMediaAccount, AppSettings, FlowConfig
from models.sync import SyncRequest, SyncAssistant
from services.scheduler import SchedulerService
from services.logger_service import LoggerService
from datetime import datetime
import json

router = APIRouter(
    prefix="/api/sync",
    tags=["Sync"]
)

@router.post("/")
async def sync_assistants(payload: SyncRequest, session: AsyncSession = Depends(get_session)):
    """
    Receives the full state of assistants from the Frontend.
    Updates the Scheduler and SocialMediaAccounts to match.
    """
    try:
        LoggerService.info(f"🔄 Sync Request Received from {payload.client_id} with {len(payload.assistants)} assistants.")
        
        # 0. Sync AppSettings (AI Configs)
        if payload.ai_configs is not None:
             settings = (await session.execute(select(AppSettings))).scalars().first()
             if not settings:
                 settings = AppSettings(id=1)
                 session.add(settings)
             
             # LoggerService.info(f"💾 Syncing {len(payload.ai_configs)} AI Configs")
             settings.ai_configs = payload.ai_configs
             
             # Sync NCA API URL if present in credentials of any assistant
             for assistant in payload.assistants:
                 if assistant.credentials and assistant.credentials.env_vars:
                     nca_url = assistant.credentials.env_vars.get("nca_api_url") or assistant.credentials.env_vars.get("ncaApiUrl")
                     if nca_url:
                         settings.nca_api_url = nca_url
                         break
             
             session.add(settings)
        
        # 1. Iterate and Upsert Jobs + Extract Accounts
        all_social_accounts = {} # platform_pageid -> account_dict
        
        for assistant in payload.assistants:
            if assistant.credentials:
                LoggerService.info(f"🔍 SYNC DEBUG: Creds for {assistant.name} -> Provider: {assistant.credentials.provider}, Key: {assistant.credentials.gemini_key[:5]}...")
            
            # 1. DB Persistence
            await _persist_assistant_to_db(assistant, session)
            
            # 2. Scheduler Update
            SchedulerService.upsert_job(assistant)
            
            # 3. Extract accounts from credentials
            if assistant.credentials and assistant.credentials.social_accounts:
                for acc in assistant.credentials.social_accounts:
                    key = f"{acc.get('platform')}_{acc.get('page_id') or acc.get('id')}"
                    all_social_accounts[key] = acc

        # 1.5 Process Top-Level Accounts (if any)
        if payload.social_accounts:
            for acc in payload.social_accounts:
                key = f"{acc.get('platform')}_{acc.get('page_id') or acc.get('id')}"
                all_social_accounts[key] = acc

        # 2. Upsert Social Accounts into DB
        for key, acc_data in all_social_accounts.items():
            acc_id = str(acc_data.get('id'))
            page_id = str(acc_data.get('page_id')) if acc_data.get('page_id') else None
            
            # Try to find existing by ID or page_id
            statement = select(SocialMediaAccount).where(
                (SocialMediaAccount.id == acc_id) | 
                (SocialMediaAccount.page_id == page_id)
            )
            results = await session.execute(statement)
            existing = results.scalars().first()
            
            if existing:
                # Update
                existing.account_name = acc_data.get('name', existing.account_name)
                existing.access_token = acc_data.get('access_token', existing.access_token)
                existing.handle = acc_data.get('handle', existing.handle)
                existing.refresh_token = acc_data.get('refresh_token', existing.refresh_token)
                existing.client_id = acc_data.get('client_id', existing.client_id)
                existing.client_secret = acc_data.get('client_secret', existing.client_secret)
                session.add(existing)
            else:
                # Create New
                new_acc = SocialMediaAccount(
                    id=acc_id,
                    platform=acc_data.get('platform'),
                    account_name=acc_data.get('name'),
                    handle=acc_data.get('handle') or acc_data.get('name'),
                    access_token=acc_data.get('access_token'),
                    page_id=page_id,
                    refresh_token=acc_data.get('refresh_token'),
                    client_id=acc_data.get('client_id'),
                    client_secret=acc_data.get('client_secret')
                )
                session.add(new_acc)
        
        await session.commit()
        return {"status": "success", "synced_count": len(payload.assistants)}

    except Exception as e:
        LoggerService.error(f"Sync Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def _persist_assistant_to_db(assistant: SyncAssistant, session: AsyncSession):
    """
    Helper to map SyncAssistant (DTO) -> FlowConfig (SQLModel) and save to DB.
    """
    try:
        # Try to find existing
        flow_id = assistant.id
        flow = await session.get(FlowConfig, flow_id)
        
        if not flow:
            # Check by name fallback if ID is new
            flow = (await session.execute(select(FlowConfig).where(FlowConfig.name == assistant.name))).scalars().first()
            if flow:
                # If found by name but ID is different, update the ID to match frontend (dangerous but requested for sync parity)
                # Actually better to just use the existing flow and update everything else
                pass
        
        # Mapping Logic
        raw = assistant.config.raw_config or {}
        
        if not flow:
            flow = FlowConfig(id=flow_id, name=assistant.name, source_type=assistant.flow_type)
        
        # Core Identity
        flow.name = assistant.name
        flow.is_active = assistant.schedule.enabled
        flow.target_page_ids = raw.get("targetPageIds", raw.get("targets", []))
        flow.ai_config_id = raw.get("aiConfigId", assistant.config.ai_config_id)
        flow.image_gen_config_id = raw.get("imageGenConfigId", assistant.config.image_gen_config_id)
        
        # Schedule
        flow.schedule_frequency = raw.get("scheduleFrequency", "Daily")
        flow.posting_time = raw.get("postingTime", "09:00")
        flow.fixed_times = raw.get("fixedTimes", assistant.schedule.fixed_times or ["09:00"])
        flow.enable_quiet_hours = raw.get("enableQuietHours", False)
        flow.posting_window_start = raw.get("postingWindowStart", "09:00")
        flow.posting_window_end = raw.get("postingWindowEnd", "21:00")
        
        # Module Specifics
        flow.video_automation_config = raw.get("video_automation_config")
        flow.image_caption_config = raw.get("imageCaptionConfig")
        flow.rss_feeds = raw.get("rssFeeds", [])
        flow.ai_topic_prompt = raw.get("aiTopicPrompt")
        
        # Metadata / Transformation
        flow.rewrite_policy = raw.get("rewritePolicy", "AI_DIRECT")
        flow.hashtag_strategy = raw.get("hashtagStrategy", "AUTO")
        flow.post_template = raw.get("postTemplate")
        flow.custom_ai_prompt = raw.get("customAiPrompt")
        flow.daily_limit = raw.get("dailyLimit")
        flow.content_tone = raw.get("contentTone")
        flow.max_items_per_refresh = raw.get("maxItemsPerRefresh", 5)
        flow.min_articles_required = raw.get("minArticlesRequired", 1)
        flow.posting_order = raw.get("postingOrder", "NEWEST_FIRST")
        flow.feed_added_timestamp = raw.get("feedAddedTimestamp")
        flow.fallback_action = raw.get("fallbackAction", "MOVE_TO_REVIEW")

        # FIX: Ensure DateTimes are not strings (SQLite loading issue)
        # Only set created_at if it's missing or if we are creating a new flow
        if not flow.created_at:
             flow.created_at = datetime.utcnow()
        elif isinstance(flow.created_at, str):
            try:
                flow.created_at = datetime.fromisoformat(flow.created_at.replace('Z', '+00:00'))
            except:
                flow.created_at = datetime.utcnow() # Fallback
                
        if flow.last_run_at and isinstance(flow.last_run_at, str):
            try:
                flow.last_run_at = datetime.fromisoformat(flow.last_run_at.replace('Z', '+00:00'))
            except:
                flow.last_run_at = None

        # Use merge() for upsert behavior - prevents UNIQUE constraint errors
        await session.merge(flow)
        # Session commit is handled by the caller
        return flow
    except Exception as e:
        LoggerService.error(f"Failed to persist assistant {assistant.name}: {e}")
        return None

@router.put("/assistant")
async def upsert_assistant(payload: SyncRequest, session: AsyncSession = Depends(get_session)):
    """
    Atomic Upsert: Syncs a SINGLE assistant and its dependencies.
    Does NOT prune other jobs.
    """
    try:
        if not payload.assistants or len(payload.assistants) != 1:
            raise HTTPException(status_code=400, detail="Atomic sync requires exactly one assistant.")

        assistant = payload.assistants[0]
        LoggerService.info(f"⚡ Atomic Sync: {assistant.name} ({assistant.id})")

        # 1. DB Persistence (Crucial for parity)
        await _persist_assistant_to_db(assistant, session)

        # 2. Sync AppSettings (AI Configs) - append/update only provided ones
        if payload.ai_configs:
             settings = (await session.execute(select(AppSettings))).scalars().first()
             if not settings:
                 settings = AppSettings(id=1, ai_configs=[])
                 session.add(settings)
             
             # Merge/Update provided configs
             current_configs = {c['id']: c for c in (settings.ai_configs or [])}
             for new_cfg in payload.ai_configs:
                 current_configs[new_cfg['id']] = new_cfg
             
             settings.ai_configs = list(current_configs.values())
             session.add(settings)

        # 3. Upsert Job (Scheduler)
        SchedulerService.upsert_job(assistant)

        # 4. Sync Accounts (Atomic)
        if assistant.credentials and assistant.credentials.social_accounts:
            for acc_data in assistant.credentials.social_accounts:
                # Reuse existing logic for account upsert (refactor if needed, but inline is safe for now)
                acc_id = str(acc_data.get('id'))
                page_id = str(acc_data.get('page_id')) if acc_data.get('page_id') else None
                
                statement = select(SocialMediaAccount).where(
                    (SocialMediaAccount.id == acc_id) | 
                    (SocialMediaAccount.page_id == page_id)
                )
                results = await session.execute(statement)
                existing = results.scalars().first()
                
                if existing:
                    existing.account_name = acc_data.get('name', existing.account_name)
                    existing.access_token = acc_data.get('access_token', existing.access_token)
                    existing.handle = acc_data.get('handle', existing.handle)
                    existing.refresh_token = acc_data.get('refresh_token', existing.refresh_token)
                    existing.client_id = acc_data.get('client_id', existing.client_id)
                    existing.client_secret = acc_data.get('client_secret', existing.client_secret)
                    session.add(existing)
                else:
                    new_acc = SocialMediaAccount(
                        id=acc_id,
                        platform=acc_data.get('platform'),
                        account_name=acc_data.get('name'),
                        handle=acc_data.get('handle') or acc_data.get('name'),
                        access_token=acc_data.get('access_token'),
                        page_id=page_id,
                        refresh_token=acc_data.get('refresh_token'),
                        client_id=acc_data.get('client_id'),
                        client_secret=acc_data.get('client_secret')
                    )
                    session.add(new_acc)

        await session.commit()
        return {"status": "success", "id": assistant.id, "action": "upsert"}

    except Exception as e:
        LoggerService.error(f"Atomic Sync Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status/{assistant_id}")
async def get_status(assistant_id: str):
    """
    Get execution logs and status for an assistant.
    Filters global logs for this specific ID.
    """
    # Get last 50 logs
    all_logs = LoggerService.get_logs(limit=100)
    
    # Filter by assistant_id (if logged with context)
    # Our LoggerService stores 'data' but maybe not distinct 'flow_id' column unless we parse or change logger.
    # Current LoggerService.log(..., data={'flow_id': ...})
    
    # Let's simple filter where message contains ID or data has ID
    assistant_logs = []
    for log in all_logs:
        # Check data dict
        data = log.get("data", {})
        if isinstance(data, dict) and data.get("flow_id") == assistant_id:
            assistant_logs.append(log)
        # Check message text fallback
        elif assistant_id in log["message"]:
             assistant_logs.append(log)
             
    # Sort logs by timestamp (newest first)
    assistant_logs.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
             
    return {
        "id": assistant_id,
        "active": True, # TODO: Check Scheduler
        "logs": assistant_logs
    }
from pydantic import BaseModel, Field

class ControlRequest(BaseModel):
    assistant_id: str
    action: str = Field(..., description="START | STOP | PAUSE | RESUME")

@router.post("/control")
async def control_assistant(request: ControlRequest):
    """
    Remote Control for Assistants.
    """
    try:
        LoggerService.info(f"🕹️ Control Request: {request.action} for {request.assistant_id}")
        
        if request.action == "START":
            # "Run Now" - independent of schedule
            # Trigger via SchedulerService
            SchedulerService.trigger_job_now(request.assistant_id)
            return {"status": "triggered", "message": "Manual execution started"}
            
        elif request.action == "PAUSE":
            SchedulerService.pause_job(request.assistant_id)
            return {"status": "paused"}
            
        elif request.action == "RESUME":
            SchedulerService.resume_job(request.assistant_id)
            return {"status": "resumed"}
            
        else:
            raise HTTPException(status_code=400, detail="Invalid Action")
            
    except Exception as e:
        LoggerService.error(f"Control Failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

