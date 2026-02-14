import logging
import asyncio
import uuid
from datetime import datetime, timedelta
from .logger_service import LoggerService
from .rss import RSSService
from .ai import ContentService
from .facebook import FacebookService
from .ncakit import NcaKitService
from .video_ai import VideoAiService
from .youtube import YouTubeService
from .storage import StorageService # Using StorageService to access DB if needed, or direct
from models.sync import SyncAssistant
# We might need direct DB access for persistent history if not using API-only
from database import async_session
from models import GeneratedPost, JobType, Job, JobStatus, AppSettings, SocialMediaAccount
from sqlmodel import select

logger = logging.getLogger(__name__)

class ExecutionPipeline:
    """
    The Brain that executes the flows triggered by the Scheduler.
    Now fully robust with logic ported from the old SchedulerService.
    """
    # STRICT WORKER CONFIG: 
    # 2 SLOTS for business tasks (Video, RSS, AI Topic)
    # The 3rd slot is implicitly permanent for System tasks (ProcessPendingJobs)
    _task_semaphore = asyncio.Semaphore(2)
    
    @staticmethod
    async def execute_flow(assistant_config: dict):
        flow_id = assistant_config.get("id")
        flow_name = assistant_config.get("name")
        flow_type = assistant_config.get("flow_type")
        
        # Limit concurrency for business tasks
        if ExecutionPipeline._task_semaphore.locked():
             LoggerService.info(f"⏳ Waiting for available worker slot: {flow_name}", flow_id=flow_id)

        async with ExecutionPipeline._task_semaphore:
            LoggerService.info(f"🚀 EXECUTION STARTED: {flow_name} ({flow_type})", flow_id=flow_id)
            
            try:
                # --- PHASE 1: SETUP ---
                config = assistant_config.get("config", {})
                credentials = assistant_config.get("credentials", {})

                # --- PHASE 2: ROUTING ---
                if flow_type == 'RSS_POST':
                    await ExecutionPipeline._run_rss_flow(flow_id, config, credentials)
                elif flow_type == 'AI_TOPIC':
                    await ExecutionPipeline._run_ai_topic_flow(flow_id, config, credentials)
                elif flow_type == 'VIDEO_AUTO':
                    await ExecutionPipeline._run_video_flow(flow_id, config, credentials)
                elif flow_type == 'IMAGE_CAPTION':
                    await ExecutionPipeline._run_image_caption_flow(flow_id, config, credentials)
                else:
                    raise ValueError(f"Unknown Flow Type: {flow_type}")
                    
                LoggerService.success(f"✅ EXECUTION COMPLETE: {flow_name}", flow_id=flow_id)
                
            except Exception as e:
                import traceback
                error_detail = str(e) or type(e).__name__
                msg = f"❌ EXECUTION FAILED: {error_detail}"
                LoggerService.error(msg, flow_id=flow_id, error=e)
                # Log traceback to console for deep debugging
                print(f"[PIPELINE ERROR] Traceback:\n{traceback.format_exc()}")
            
    # --- HELPER: Credential Resolution ---
    @staticmethod
    def _resolve_credential(credentials: dict, platform: str, target_id: str = None) -> dict:
        """
        Finds the specific credentials for a Platform + Target (Page/Account).
        Prioritizes the 'social_accounts' list, then DB fallback, then legacy global keys.
        """
        accounts = credentials.get("social_accounts", [])
        
        # DEBUG: Log what we're searching for
        LoggerService.info(f"🔍 RESOLVING: Platform={platform}, TargetID={target_id}, Available accounts: {len(accounts)}")
        
        # 1. Try Specific Match in Social Accounts (by page_id OR by id)
        for acc in accounts:
            if acc.get("platform") != platform:
                continue
            
            acc_page_id = str(acc.get("page_id", ""))
            acc_id = str(acc.get("id", ""))
            target_str = str(target_id) if target_id else ""
            
            # Match by page_id
            if target_str and acc_page_id == target_str:
                LoggerService.info(f"✅ Found match by page_id: {acc_page_id}")
                return acc
            
            # Match by internal ID
            if target_str and acc_id == target_str:
                LoggerService.info(f"✅ Found match by id: {acc_id}")
                return acc
                
        # 2. Fallback: Return the *first* account of that platform if no target specified
        if not target_id:
            for acc in accounts:
                if acc.get("platform") == platform:
                    LoggerService.info(f"✅ Using first {platform} account (no target specified)")
                    return acc

        # 3. DB FALLBACK: Fetch directly from SocialMediaAccount table
        # This is critical when scheduler passes stale credentials or for direct ID lookup
        if target_id:
            try:
                import asyncio
                from database import sync_session
                from models import SocialMediaAccount
                
                with sync_session() as session:
                    from sqlalchemy import select, or_
                    # Generic lookup by ID or Page ID
                    stmt = select(SocialMediaAccount).where(
                        or_(
                            SocialMediaAccount.page_id == str(target_id),
                            SocialMediaAccount.id == str(target_id)
                        )
                    )
                    acc = session.execute(stmt).scalars().first()
                    
                    # Verify Platform Match if platform is specified
                    if acc and platform:
                         # Handle Enum vs String comparison
                         acc_platform = str(acc.platform.value) if hasattr(acc.platform, 'value') else str(acc.platform)
                         if acc_platform.upper() != platform.upper():
                             LoggerService.warn(f"⚠️ Account found but platform mismatch. Expected {platform}, found {acc_platform}")
                             acc = None

                    if acc:
                        LoggerService.info(f"✅ Found in DB: {acc.account_name} ({acc.platform})")
                        return {
                            "id": str(acc.id),
                            "platform": str(acc.platform),
                            "page_id": acc.page_id,
                            "page_name": acc.account_name,
                            "access_token": acc.access_token,
                            "refresh_token": acc.refresh_token,
                            "client_id": acc.client_id,
                            "client_secret": acc.client_secret
                        }
                    else:
                        LoggerService.warn(f"⚠️ No account found in DB for target_id: {target_id}")
            except Exception as e:
                LoggerService.error(f"DB Fallback Failed: {e}")
        
        # 4. Legacy Flat Fields Fallback
        if platform == "FACEBOOK":
            if credentials.get("fb_token"):
                return {"access_token": credentials.get("fb_token")}
            LoggerService.warn(f"⚠️ No FB token found anywhere for target: {target_id}")
            return {}
            
        if platform == "GEMINI":
             if credentials.get("provider") == "Groq":
                 LoggerService.info(f"🔍 FOUND GROQ CREDENTIALS: {credentials.get('gemini_key')[:5]}...")
             
             return {
                 "api_key": credentials.get("gemini_key"),
                 "model": credentials.get("model"),
                 "provider": credentials.get("provider", "Gemini"),
                 "base_url": credentials.get("base_url")
             }
        
        return {}

    @staticmethod
    def _resolve_targets(config: dict) -> list:
        """
        Robustly extracts target IDs from config, handling camelCase, snake_case, 
        and legacy single ID fields.
        """
        raw = config.get("raw_config", {})
        
        # 1. Try Collection fields
        targets = raw.get("targetPageIds") or config.get("targetPageIds")
        if not targets:
            targets = raw.get("targets") or config.get("targets")
        
        # 2. Try Single ID fields
        if not targets:
            # Check various naming conventions across revisions
            single = raw.get("targetId") or raw.get("targetPageId") or config.get("targetPageId")
            if single:
                targets = [single]
        
        # 3. Final Sanity & Type Check
        if not targets:
            return []
            
        if isinstance(targets, str):
            try:
                import json
                if targets.startswith("["):
                    targets = json.loads(targets)
                else:
                    targets = [targets]
            except:
                targets = [targets]
        
        # Deduplicate & Filter
        return list(set([str(t) for t in targets if t]))


    # --- WORKERS ---

    @staticmethod
    async def create_manual_job(payload: dict, is_queue: bool = False, session=None):
        """
        Creates a job for manual publishing with resolved credentials.
        """
        from database import async_session
        from models import Job, JobType, JobStatus
        from datetime import datetime

        local_session = False
        if session is None:
             session = async_session()
             local_session = True
        
        try:
            # We create one job per account or one big job? 
            # The previous logic created one job per account. 
            # Let's stick to that for granular tracking, OR use a single job with multiple targets.
            # Single job is better for "Generation" flow, but for direct publish, 
            # individual feedback is better. 
            
            # Use the "accounts_data" we prepared in api.py
            accounts_data = payload.get("accounts_data", [])
            caption = payload.get("caption")
            media_path = payload.get("file_path")
            hf_url = payload.get("hf_url")
            video_type = payload.get("video_type")
            video_title = payload.get("video_title")
            
            success_count = 0
            
            for acc in accounts_data:
                # 1. Create Job Payload
                job_payload = {
                    "platform": acc["platform"],
                    "access_token": acc["access_token"],
                    "page_id": acc["page_id"],
                    "accountId": acc["id"], # For reference
                    "caption": caption,
                    "mediaPath": media_path,
                    "hfUrl": hf_url,
                    "videoType": video_type,
                    "videoTitle": video_title
                }
                
                # 2. Create Job
                new_job = Job(
                    type=JobType.FB_PUBLISH, # Reusing existing type
                    payload=job_payload,
                    status=JobStatus.PENDING,
                    scheduled_at=datetime.utcnow()
                )
                session.add(new_job)
                success_count += 1
                
            await session.commit()
            LoggerService.info(f"Created {success_count} Manual Jobs")
            
        except Exception as e:
            if local_session:
                await session.rollback()
            raise e
        finally:
            if local_session:
                await session.close()

    @staticmethod
    async def execute_manual_publish(payload: dict) -> list:
        """
        Immediately executes the publish action for all targets and returns results.
        Bypasses the Scheduler/JobQueue for instant feedback.
        """
        accounts_data = payload.get("accounts_data", [])
        caption = payload.get("caption")
        media_path = payload.get("file_path")
        hf_url = payload.get("hf_url")
        video_type = payload.get("video_type", "regular")
        video_title = payload.get("video_title", "Untitled")
        
        results = []
        
        for acc in accounts_data:
            page_id = acc.get("page_id")
            access_token = acc.get("access_token")
            acc_name = acc.get("account_name", page_id)
            
            result = {
                "account": acc_name,
                "id": acc.get("id"),
                "status": "failed",
                "postId": None,
                "error": None
            }
            
            try:
                # 1. Determine Content Type
                if media_path or hf_url:
                    # Media Post
                    target_path = media_path if media_path else hf_url
                    
                    if target_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
                        # Video
                        if video_type == 'reel':
                            await FacebookService.upload_reel(page_id, access_token, target_path, caption)
                            result["postId"] = "reel_published" # Reels API return is bool
                        else:
                            # Regular Video
                            vid_id = await FacebookService.upload_video(page_id, access_token, target_path, video_title, caption)
                            result["postId"] = vid_id
                    else:
                        # Photo (Default if not video)
                        res = await FacebookService.upload_photo(page_id, access_token, target_path, caption)
                        result["postId"] = res.get("id") or res.get("post_id")
                else:
                    # Text Post
                    res = await FacebookService.publish_text(page_id, access_token, caption)
                    result["postId"] = res.get("id")
                
                result["status"] = "success"
                
            except Exception as e:
                import traceback
                error_msg = f"{type(e).__name__}: {str(e)}"
                if not str(e):
                    error_msg = f"{type(e).__name__}: {repr(e)}"
                
                print(f"DEBUG: Immediate Publish Error for {acc_name}: {error_msg}")
                traceback.print_exc()
                result["error"] = error_msg
                LoggerService.error(f"Immediate Publish Failed for {acc_name}: {error_msg}")
                
            results.append(result)
            
        return results

    @staticmethod
    async def _run_rss_flow(flow_id: str, config: dict, credentials: dict):
        """
        Fetches RSS, Summarizes with AI, Posts to FB.
        FULLY UPGRADED:
        1. Uses feed_added_timestamp for Deduplication.
        2. Only posts the LATEST item (User Requirement).
        3. Updates DB after successful post to prevent duplicates.
        """
        from database import async_session
        from models import FlowConfig
        from sqlalchemy import select
        from dateutil import parser as date_parser
        import time

        urls = config.get("rss_urls", [])
        if not urls:
            LoggerService.warn("No RSS URLs provided.", flow_id=flow_id)
            return

        # 1. Fetch Current State from DB
        async with async_session() as session:
            flow_obj = await session.get(FlowConfig, flow_id)
            if not flow_obj:
                LoggerService.error(f"Flow {flow_id} not found in DB", flow_id=flow_id)
                return
            
            last_timestamp = flow_obj.feed_added_timestamp or 0.0
            LoggerService.info(f"Checking RSS for items newer than timestamp: {last_timestamp}", flow_id=flow_id)

            # 2. Fetch & Aggregate Items
            all_items = []
            for url in urls:
                LoggerService.info(f"Fetching RSS: {url}", flow_id=flow_id)
                try:
                    items = RSSService.fetch_feed(url)
                    all_items.extend(items)
                except Exception as e:
                    LoggerService.error(f"Failed to fetch {url}: {e}", flow_id=flow_id)
                
            if not all_items:
                LoggerService.info("No items found in RSS feeds.", flow_id=flow_id)
                return

            # 3. Filter & Sort by Date (Newest First)
            valid_items = []
            for item in all_items:
                try:
                    # Normalize date to timestamp
                    item_dt = date_parser.parse(item.pubDate)
                    item_ts = item_dt.timestamp()
                    
                    if item_ts > last_timestamp:
                        valid_items.append((item_ts, item))
                except Exception as e:
                    LoggerService.warn(f"Failed to parse date for item {item.link}: {e}")

            # Sort DESC by timestamp
            valid_items.sort(key=lambda x: x[0], reverse=True)

            if not valid_items:
                LoggerService.info("No NEW items found since last execution.", flow_id=flow_id)
                return

            # 4. Pick ONLY the LATEST item (User Request: "শুধু লেটেস্ট পোস্ট করবে")
            newest_ts, newest_item = valid_items[0]
            LoggerService.info(f"🚀 Newest Item Found: {newest_item.title} (TS: {newest_ts})", flow_id=flow_id)

            # 5. AI Rewrite
            gemini_creds = ExecutionPipeline._resolve_credential(credentials, "GEMINI")
            ai_key = gemini_creds.get("api_key")
            ai_provider = gemini_creds.get("provider", "Gemini")
            ai_model = gemini_creds.get("model")
            ai_base_url = gemini_creds.get("base_url")
            
            # User Configuration for RSS
            raw_config = config.get("raw_config", {})
            rewrite_policy = raw_config.get("rewritePolicy", "AI_REWRITE")
            custom_prompt = raw_config.get("customAiPrompt")
            
            content = f"{newest_item.title}\n\n{newest_item.description}\n\n{newest_item.link}"
            
            if ai_key and rewrite_policy != "ORIGINAL":
                LoggerService.info(f"Rewriting item with {ai_provider}...", flow_id=flow_id)
                prompt = custom_prompt if custom_prompt else f"Rewrite this news item for a viral Facebook post. Keep it engaging:\n\nTitle: {newest_item.title}\nNews: {newest_item.description}"
                
                try:
                    if ai_provider == "Groq":
                        content = await ContentService.generate_with_groq(ai_key, prompt, model=ai_model, base_url=ai_base_url)
                    elif ai_provider == "OpenRouter":
                        content = await ContentService.generate_with_openrouter(ai_key, prompt, model=ai_model, base_url=ai_base_url)
                    else:
                        content = await ContentService.generate_with_gemini(ai_key, prompt, model=ai_model)
                    
                    # Optional: Add link back if desired (usually yes for RSS)
                    content += f"\n\n🔗 Source: {newest_item.link}"
                except Exception as e:
                    LoggerService.error(f"AI Generation Failed: {e}", flow_id=flow_id)
                    # Fallback remains original content merged above

            # 6. Post to Targets
            target_ids = ExecutionPipeline._resolve_targets(config)
            
            if not target_ids:
                LoggerService.warn("Skipping Post: No Target Pages found", flow_id=flow_id)
                return

            posted_count = 0
            for page_id in target_ids:
                cred = ExecutionPipeline._resolve_credential(credentials, "FACEBOOK", page_id)
                fb_token = cred.get("access_token")
                
                if fb_token:
                    try:
                        LoggerService.info(f"Publishing to FB Page {page_id}...", flow_id=flow_id)
                        await FacebookService.publish_text(page_id, fb_token, content)
                        posted_count += 1
                    except Exception as e:
                        LoggerService.error(f"Failed to post to {page_id}: {e}", flow_id=flow_id)

            # 7. UPDATE DB TIMESTAMP (Critical for Deduplication)
            if posted_count > 0:
                flow_obj.feed_added_timestamp = newest_ts
                session.add(flow_obj)
                await session.commit()
                LoggerService.success(f"RSS Flow Complete. Last posted timestamp updated to {newest_ts}", flow_id=flow_id)
            else:
                LoggerService.warn("No successful posts made. Timestamp NOT updated.", flow_id=flow_id)

    @staticmethod
    async def _run_ai_topic_flow(flow_id: str, config: dict, credentials: dict):
        """
        Generates a post from a Topic/Niche.
        """
        prompt = config.get("prompt") or config.get("niche")
        if not prompt: return
        
        gemini_creds = ExecutionPipeline._resolve_credential(credentials, "GEMINI")
        ai_key = gemini_creds.get("api_key")
        ai_provider = gemini_creds.get("provider", "Gemini")
        ai_model = gemini_creds.get("model")
        ai_base_url = gemini_creds.get("base_url")

        if not ai_key: 
            LoggerService.error("Missing AI Key", flow_id=flow_id)
            return
            
        LoggerService.info(f"Generating Topic Post with {ai_provider}: {prompt}", flow_id=flow_id)
        
        system_instructions = f"Write a Facebook post about: {prompt}"
        
        try:
            if ai_provider == "Groq":
                final_post = await ContentService.generate_with_groq(ai_key, system_instructions, model=ai_model, base_url=ai_base_url)
            elif ai_provider == "OpenRouter":
                final_post = await ContentService.generate_with_openrouter(ai_key, system_instructions, model=ai_model, base_url=ai_base_url)
            else:
                final_post = await ContentService.generate_with_gemini(ai_key, system_instructions, model=ai_model)
            
            # Post
            raw_config = config.get("raw_config", {})
            targets = raw_config.get("targets", []) 
            if not targets and raw_config.get("targetPageId"):
                targets = [raw_config.get("targetPageId")]
                
            for page_id in targets:
                cred = ExecutionPipeline._resolve_credential(credentials, "FACEBOOK", page_id)
                fb_token = cred.get("access_token")
                
                if fb_token:
                    await FacebookService.publish_text(page_id, fb_token, final_post)
        except Exception as e:
             LoggerService.error(f"AI Topic Generation Failed: {e}", flow_id=flow_id)

    @staticmethod
    async def _run_image_caption_flow(flow_id: str, config: dict, credentials: dict):
        """
        Generates an Image + Caption and posts to FB.
        """
        LoggerService.info("Starting Image Caption Flow...", flow_id=flow_id)
        
        # 1. Resolve Configs
        raw_config = config.get("raw_config", {})
        icc = raw_config.get("imageCaptionConfig") or {}
        
        system_prompt = icc.get("systemPrompt", "You are an AI art director.")
        niche = icc.get("niche", "trending topics")
        style = icc.get("imageStyle", "photorealistic")
        size = icc.get("imageSize", "1024x1024")
        generate_caption = icc.get("generateCaption", True)
        caption_instruction = icc.get("captionInstruction", "Write a short engaging caption.")

        # 2. Get Image Generator Config
        image_gen_id = raw_config.get("imageGenConfigId")
        # We need AppSettings to find the actual provider/key
        from database import async_session
        from models import AppSettings
        
        async with async_session() as session:
            settings = (await session.execute(select(AppSettings))).scalars().first()
            if not settings or not settings.image_gen_configs:
                raise Exception("No Image Generation Configs found in Settings")
            
            # Find the specific config
            img_cfg = next((c for c in settings.image_gen_configs if c["id"] == image_gen_id), settings.image_gen_configs[0])
            
            provider = img_cfg["provider"]
            api_key = img_cfg["apiKey"]
            worker_url = img_cfg.get("workerUrl")
            model = img_cfg.get("model")

            # Override model if specified in flow config (e.g. specific Cloudflare model)
            if raw_config.get("imageGenModel"):
                model = raw_config.get("imageGenModel")

            # 3. Generate Image
            prompt = f"{system_prompt}. Subject: {niche}. Style: {style}."
            LoggerService.info(f"Generating image with {provider}...", flow_id=flow_id)
            image_bytes = await ContentService.generate_image(provider, api_key, prompt, worker_url, model=model)
            
            # Save temporary image
            import os
            import uuid
            os.makedirs("static/uploads", exist_ok=True)
            image_path = f"static/uploads/auto_{uuid.uuid4()}.png"
            with open(image_path, "wb") as f:
                f.write(image_bytes)
            
            # 4. (Optional) Generate Caption
            final_caption = ""
            if generate_caption:
                gemini_creds = ExecutionPipeline._resolve_credential(credentials, "GEMINI")
                ai_key = gemini_creds.get("api_key")
                ai_provider = gemini_creds.get("provider", "Gemini")
                ai_model = gemini_creds.get("model")
                ai_base_url = gemini_creds.get("base_url")

                if ai_key:
                    LoggerService.info(f"Generating caption with {ai_provider}...", flow_id=flow_id)
                    caption_prompt = f"Based on this art direction: '{prompt}', write a Facebook caption: {caption_instruction}"
                    
                    try:
                        if ai_provider == "Groq":
                            final_caption = await ContentService.generate_with_groq(ai_key, caption_prompt, model=ai_model, base_url=ai_base_url)
                        elif ai_provider == "OpenRouter":
                            final_caption = await ContentService.generate_with_openrouter(ai_key, caption_prompt, model=ai_model, base_url=ai_base_url)
                        else:
                            final_caption = await ContentService.generate_with_gemini(ai_key, caption_prompt, model=ai_model)
                    except Exception as e:
                        LoggerService.error(f"Caption Generation Failed: {e}", flow_id=flow_id)

            # 5. Post to Targets
            targets = raw_config.get("targetPageIds") or []
            if not targets and raw_config.get("targetPageId"):
                targets = [raw_config.get("targetPageId")]
            
            # Deduplicate targets ensuring unique page IDs
            targets = list(set(targets))
            
            for page_id in targets:
                cred = ExecutionPipeline._resolve_credential(credentials, "FACEBOOK", page_id)
                fb_token = cred.get("access_token")
                
                if fb_token:
                    LoggerService.info(f"Uploading Image to FB Page {page_id}...", flow_id=flow_id)
                    await FacebookService.upload_photo(page_id, fb_token, image_path, final_caption)
                else:
                    LoggerService.warn(f"Skipping FB Upload for {page_id}: Missing Token", flow_id=flow_id)

    @staticmethod
    async def _run_video_flow(flow_id: str, config: dict, credentials: dict):
        """
        Complex Video Automation Flow.
        FULLY UPGRADED to use all FlowConfig parameters.
        Includes Ultra-Verbose Logging for Debugging.
        """
        import json
        
        def log_step(step, msg, data=None):
            if data:
                try:
                    dump = json.dumps(data, indent=2, default=str)
                    LoggerService.info(f"📜 [STEP {step}] {msg}\nDATA:\n{dump}", flow_id=flow_id)
                except:
                    LoggerService.info(f"📜 [STEP {step}] {msg}\nDATA: {str(data)}", flow_id=flow_id)
            else:
                LoggerService.info(f"🔹 [STEP {step}] {msg}", flow_id=flow_id)

        log_step(0, "Starting Video Flow - Initial Config", config)
        
        # 1. Extract Configs (with fallbacks)
        vac = config.get("video_automation_config") or {}
        log_step(1, "Extracted Video Automation Config", vac)
        
        # Core Params - Base
        module = vac.get("module", "short-video") 
        niche = vac.get("niche") or config.get("niche", "General")
        
        # NOTE: Specific params (voice, style, etc) will be extracted PER MODULE
        # to ensure strictness and valid data usage. 
        
        # AI Config Resolution
        # AI Config Resolution
        ai_config_id = config.get("ai_config_id")
        
        # Default Fallback
        gemini_creds = ExecutionPipeline._resolve_credential(credentials, "GEMINI")
        ai_provider = gemini_creds.get("provider", "Gemini")
        ai_key = gemini_creds.get("api_key")
        ai_model = gemini_creds.get("model") or "gemini-2.0-flash"
        ai_base_url = gemini_creds.get("base_url")

        # Try to find specific config if ID provided
        if ai_config_id:
            from database import async_session
            from models import AppSettings
            from sqlalchemy import select
            
            async with async_session() as session:
                settings = (await session.execute(select(AppSettings))).scalars().first()
                if settings and settings.ai_configs:
                    specific_cfg = next((c for c in settings.ai_configs if str(c.get("id")) == str(ai_config_id)), None)
                    if specific_cfg:
                        ai_provider = specific_cfg.get("provider")
                        ai_key = specific_cfg.get("apiKey")
                        ai_model = specific_cfg.get("model")
                        ai_base_url = specific_cfg.get("baseUrl")
                        LoggerService.info(f"Using Custom AI Config: {ai_provider} ({ai_model})", flow_id=flow_id)
                    else:
                         LoggerService.warn(f"AI Config ID {ai_config_id} not found in DB settings", flow_id=flow_id)
                else:
                    LoggerService.warn("No AI Configs found in DB settings", flow_id=flow_id)
        
        # NCA URL Resolution
        # NCA URL Resolution
        nca_url = credentials.get("nca_api_url")
        
        if not nca_url:
            # Fallback to DB Settings
            from database import async_session
            from models import AppSettings
            from sqlalchemy import select
            
            async with async_session() as session:
                settings = (await session.execute(select(AppSettings))).scalars().first()
                if settings and settings.nca_api_url:
                    nca_url = settings.nca_api_url
                    LoggerService.info(f"🌍 Using NCA URL from Global Settings: {nca_url}", flow_id=flow_id)
        
        if not nca_url:
             nca_url = "http://localhost:3000"
             LoggerService.warn("⚠️ NCA URL not found in Settings, defaulting to localhost:3000", flow_id=flow_id)
        
        if not ai_key: raise Exception("Missing Gemini Key")
        
        # 2. Concept Generation
        from services.video_ai import VideoAiService
        from services.video_prompts import CONCEPT_PROMPT_TEMPLATE
        from services.memory import MemoryService
        
        ai_config = {
            "provider": ai_provider,
            "model": ai_model,
            "api_key": ai_key,
            "base_url": ai_base_url
        }
        
        # Fetch Memory for Topic Deduplication
        from database import sync_session
        recent_ideas = []
        try:
            with sync_session() as session:
                import asyncio
                # MemoryService.get_recent_ideas is async, we need to handle it in sync context
                # but wait, the pipeline IS async mostly. execute_flow is async. 
                # Wait, this part of the method is async.
                pass 
        except: pass

        # Actually _run_video_flow is NOT async? No, it IS async.
        # Let's check the definition. Lines 580: async def _run_video_flow(...)
        
        try:
            from database import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                recent_ideas = await MemoryService.get_recent_ideas(flow_id, session, limit=30)
        except Exception as e:
            LoggerService.warn(f"⚠️ Could not fetch memory: {e}", flow_id=flow_id)

        memory_context = ", ".join(recent_ideas) if recent_ideas else "None"
        
        concept = await VideoAiService.generate_concept(
            ai_config, 
            niche=niche, 
            niche_details=vac.get("nicheDetails", niche),
            memoryContext=memory_context
        )
        LoggerService.info(f"Generated Concept: {concept}", flow_id=flow_id)
        
        # Save to memory immediately
        try:
             async with AsyncSessionLocal() as session:
                await MemoryService.save_idea(flow_id, concept, session)
        except Exception as e:
            LoggerService.warn(f"⚠️ Could not save concept to memory: {e}", flow_id=flow_id)
        
        # 3. Submit to NCA
        nca = NcaKitService(nca_url)
        video_uuid = None
        
        try:
            if module == 'short-video':
                # Extract Params for Short Video
                voice = vac.get("voice", "af_heart")
                music = vac.get("music", "calm")
                style = vac.get("style", "cinematic")
                
                # Generate Scenes using VideoAiService
                content = await VideoAiService.generate_short_video_content(ai_config, concept)
                scenes = content.get("scenes", [])
                
                # CRITICAL VALIDATION: Prevent 422 errors from empty/invalid scenes
                if not scenes or not isinstance(scenes, list) or len(scenes) == 0:
                    LoggerService.warn(f"⚠️ AI returned empty scenes. Creating fallback scene from concept.", flow_id=flow_id)
                    scenes = [{"text": concept[:200], "searchTerms": [niche]}]
                
                # Validate each scene has required fields
                valid_scenes = []
                for s in scenes:
                    if isinstance(s, dict) and s.get("text"):
                        valid_scenes.append({
                            "text": str(s.get("text", ""))[:500],  # Ensure string, limit length
                            "searchTerms": s.get("searchTerms", [niche]) if isinstance(s.get("searchTerms"), list) else [niche]
                        })
                
                if not valid_scenes:
                    LoggerService.warn(f"⚠️ No valid scenes after validation. Creating fallback.", flow_id=flow_id)
                    valid_scenes = [{"text": concept[:200], "searchTerms": [niche]}]
                
                scenes = valid_scenes
                log_step(2.5, f"Final Scenes (Count: {len(scenes)})", scenes[:2])  # Log first 2 scenes
                
                # Config for NCAKit /api/short-video (per API_DOCUMENTATION.md)
                # Keys: voice, music, musicVolume, captionPosition, captionBackgroundColor, orientation, paddingBack
                # NOTE: image_style is NOT a valid key for short-video (it's for story-reel)
                video_config = {
                    "voice": voice,
                    "music": music,
                    "musicVolume": "medium",
                    "captionPosition": "bottom",
                    "orientation": "portrait"
                }
                LoggerService.info(f"📹 Submitting Short Video to NCA: {len(scenes)} scenes, voice={voice}, music={music}", flow_id=flow_id)
                res = await nca.create_short_video(scenes=scenes, config=video_config)
                video_uuid = res.get("videoId") or res.get("job_id") or res.get("jobId") or res.get("id")



            elif module == 'story-reel':
                # Extract Params for Story Reel
                style = vac.get("style", "cinematic")
                voice = vac.get("voice", "af_heart")
            
                content = await VideoAiService.generate_story_reel_content(ai_config, concept, style)
                script = content.get("script", concept)
                image_style = content.get("image_style", style)
                
                LoggerService.info(f"📖 Submitting Story Reel to NCA: voice={voice}, image_style={image_style}, script_len={len(script)}", flow_id=flow_id)
                res = await nca.create_story_reel(
                    script=script, 
                    image_style=image_style, 
                    voice=voice
                )
                video_uuid = res.get("job_id") or res.get("videoId") or res.get("jobId") or res.get("id")

                
            elif module == 'fact-image':
                # Extract Params for Fact Image
                duration = vac.get("duration", 5) # Default to 5s if not set
                if duration > 7:
                    LoggerService.warn(f"⚠️ Fact Image duration {duration}s exceeds limit. Clamping to 7s.", flow_id=flow_id)
                    duration = 7
                
                content = await VideoAiService.generate_fact_image_content(ai_config, concept)
                res = await nca.create_fact_image(
                    model=content.get("model", "nvidia"), 
                    image_prompt=content.get("image_prompt", concept), 
                    fact_text=content.get("fact_text", concept), 
                    fact_heading=content.get("fact_heading", niche), 
                    duration=duration,
                    heading_background=content.get("heading_background")
                )
                video_uuid = res.get("job_id") or res.get("videoId") or res.get("jobId") or res.get("id")

            elif module == 'quiz':
                # Extract Params for Quiz
                scene_count = vac.get("sceneCount", 3)
                voice = vac.get("voice", "af_heart")
                
                content = await VideoAiService.generate_quiz_content(ai_config, concept, scene_count)
                res = await nca.create_quiz_reel(
                    quizzes=content.get("quizzes", []),
                    voice=voice
                )
                video_uuid = res.get("job_id") or res.get("videoId") or res.get("jobId") or res.get("id")

            elif module == 'text-story':
                # Extract Params for Text Story
                voice = vac.get("voice", "af_heart") # Voice A
                voice_b = vac.get("voiceB", "am_fenrir")
                tone = vac.get("tone", "engaging")
                scene_count = vac.get("sceneCount", 10) # Message Count
            
                content = await VideoAiService.generate_text_story_content(
                    ai_config, concept, "Person A", "Person B", scene_count, tone
                )
                res = await nca.create_text_story(
                    messages=content.get("messages", []),
                    person_a_name="Person A",
                    person_b_name="Person B",
                    voice_a=voice,
                    voice_b=voice_b,
                    ending_text=content.get("ending_text")
                )
                LoggerService.info(f"Text Story Submitted (Voice A: {voice}, Voice B: {voice_b})", flow_id=flow_id)
                video_uuid = res.get("job_id") or res.get("videoId") or res.get("jobId") or res.get("id")

            else:
                raise ValueError(f"Module {module} not supported in backend auto-flow yet.")

        except Exception as e:
             LoggerService.error(f"NCA Submission Failed: {e}", flow_id=flow_id)
             raise e

        if not video_uuid:
             raise Exception("No Job ID returned from NCA Service")

        LoggerService.info(f"Video Rendering Started: {video_uuid}", flow_id=flow_id)
        
        # 4. Polling Loop
        video_url = None
        # Increase to 120 (20 mins) for story-reels and complex videos
        ONGOING_STATUSES = [
            "queued", "processing", "generating_audio", "generating_images", 
            "composing_video", "adding_text", "creating_video", "generating_image"
        ]
        
        for i in range(120): # Wait up to 20 mins (120 * 10s)
             await asyncio.sleep(10)
             try:
                 status_data = await nca.get_status(video_uuid, module)
             except (httpx.ReadTimeout, httpx.ConnectTimeout) as timeout_err:
                 LoggerService.warn(f"⏳ [STEP 4] NCA Polling Timeout (Attempt {i}). This is usually transient as the server is busy Rendering. Retrying in 10s...")
                 continue
             except Exception as poll_err:
                 LoggerService.error(f"❌ [STEP 4] Status Polling Error: {poll_err}")
                 # For non-timeout errors, we might want to wait a bit longer or retry a few times
                 continue
             
             status = status_data.get("status")
             
             # Log reduction logic: only log every 10 attempts for ongoing statuses
             is_ongoing = status in ONGOING_STATUSES
             
             import json
             try:
                 if not is_ongoing or i % 10 == 0:
                     dump = json.dumps(status_data, indent=2, default=str)
                     LoggerService.info(f"🔄 [STEP 4] Polling Status: {status} (Attempt {i})\nDATA:\n{dump}", flow_id=flow_id)
             except:
                 if not is_ongoing or i % 10 == 0:
                     LoggerService.info(f"🔄 [STEP 4] Polling Status: {status} | Data: {status_data}", flow_id=flow_id)
             
             if status in ["success", "ready", "completed"]:
                 # 1. Try Standard Keys
                 video_url = status_data.get("video_url") or status_data.get("output") or status_data.get("videoUrl") or status_data.get("url")
                 
                 # 2. Deep Search if Missing
                 if not video_url:
                     LoggerService.warn(f"⚠️ Standard keys missing. Searching deeply in response...", flow_id=flow_id)
                     import json
                     # Quick recursive string search for http...mp4
                     str_dump = json.dumps(status_data)
                     import re
                     # Find HTTP/HTTPS url ending in mp4/mov or just from common hosting
                     urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', str_dump)
                     # Filter for likely video candidates
                     video_candidates = [u for u in urls if u.endswith(('.mp4', '.mov', '.mkv')) or 'res.cloudinary' in u or 'blob:' in u]
                     
                     if video_candidates:
                         video_url = video_candidates[0].strip('",')
                         LoggerService.info(f"🔍 Found hidden video URL: {video_url}", flow_id=flow_id)

                 # 3. --- FORCE URL FOR SHORT VIDEO ---
                 if module == "short-video":
                     # Use the local API endpoint for reliable downloads
                     video_url = f"{nca_url}/api/video/short-video/{video_uuid}"
                     LoggerService.info(f"🔗 Constructed Short Video URL: {video_url}", flow_id=flow_id)
                 
                 # 4. --- STORY REEL FALLBACK ---
                 if not video_url and module == "story-reel":
                     video_url = f"{nca_url}/api/story/story-reel/{video_uuid}"
                     LoggerService.info(f"🔗 Constructed Story Reel URL: {video_url}", flow_id=flow_id)
                 # ------------------------------------

                 if video_url:
                     break
                 else:
                     LoggerService.error(f"❌ Status is Success but NO VIDEO URL found in payload.", flow_id=flow_id)
                     
             if status == "failed":
                 err = status_data.get('error') or status_data.get('message') or "Unknown Error from NCA"
                 raise Exception(f"Video Generation Failed: {err}")
                 
        if not video_url:
            raise Exception("Step 4 Failed: Video Generation Timed Out or URL Missing")
            
        LoggerService.info(f"✅ [STEP 4] Video Ready: {video_url}", flow_id=flow_id)
        
        # 5. Upload (YouTube / FB)
        # Unified Target Resolution
        target_ids = ExecutionPipeline._resolve_targets(config)

        if not target_ids:
            LoggerService.warn("⚠️ [STEP 5] Skipped: No Target Pages found", flow_id=flow_id)
            return


        LoggerService.info(f"📤 [STEP 5] Starting Upload to {len(target_ids)} targets...", flow_id=flow_id)

        # We need to find the platform for each target_id.
        # Credential resolution usually needs platform hint.
        
        all_accounts = credentials.get("social_accounts", [])
        
        from services.social_media import SocialMediaService

        for target_id in target_ids:
             # Identify Platform from Account Data or Heuristics
             # 1. Try to find in provided accounts list
             account = next((acc for acc in all_accounts if str(acc.get("id")) == str(target_id) or str(acc.get("page_id")) == str(target_id)), None)
             
             platform = "FACEBOOK" # Default
             if account:
                 platform = account.get("platform", "FACEBOOK").upper()
             
             # 2. HEURISTIC OVERRIDE: Correct Platform based on ID format if Account data is missing/wrong
             # YouTube Channels start with 'UC'
             if str(target_id).startswith("UC") and len(str(target_id)) > 20:
                 if platform == "FACEBOOK":
                      LoggerService.warn(f"⚠️ Target {target_id} identified as YOUTUBE by ID format. Overriding default FACEBOOK platform.", flow_id=flow_id)
                 platform = "YOUTUBE"
             
             # Dailymotion IDs are usually short alphanumeric (e.g. x12345) - Risky to heuristic, but we can trust user input if explicit
             
             LoggerService.info(f"🔍 [STEP 5.1] Resolving credentials for {platform} ID: {target_id}", flow_id=flow_id)
             
             # 3. SAFETY CHECK: Prevent Cross-Posting Errors
             if platform == "FACEBOOK" and str(target_id).startswith("UC"):
                  LoggerService.error(f"❌ [STEP 5] SAFETY BLOCK: Attempted to route YOUTUBE Channel {target_id} to FACEBOOK API. Skipping.", flow_id=flow_id)
                  continue
                  
             try:
                 # Resolve Credentials using the Pipeline's helper but specifying platform
                 cred = ExecutionPipeline._resolve_credential(credentials, platform, target_id)
                 
                 # Prepare Metadata
                 caption = f"{niche} - {concept[:50]}... #AI #Shorts"
                 # FB / YT Title Limit is 100/255. We truncate to 90 to be safe
                 clean_niche = (niche or "AI Video")[:60]
                 video_title = f"{clean_niche} AI Short {uuid.uuid4().hex[:4]}"
                 video_title = video_title[:95] # Hard cap just in case
                 
                # Determine Video Type
                 # User Requirement: "All are Reels (9:16)"
                 video_type = "reel"
                 media_path = video_url
                 
                 # if module == 'fact-image':
                 #      video_type = "image"  <-- DISABLED per User Request
                 
                 LoggerService.info(f"🚀 [STEP 5.2] Publishing to {platform} ({target_id}) as {video_type}...", flow_id=flow_id)
                 
                 # Unified Publish Call
                 result = await SocialMediaService.publish(
                     platform=platform,
                     credentials=cred,
                     caption=caption,
                     media_path=media_path,
                     video_type=video_type,
                     video_title=video_title
                 )
                 
                 LoggerService.success(f"✅ [STEP 5 COMPLETE] Published to {platform} {target_id}. Result: {result}", flow_id=flow_id)
                 
             except Exception as e:
                 error_msg = str(e) or repr(e)
                 LoggerService.error(f"❌ [STEP 5 FAILED] Upload Error for {target_id}: {error_msg}", flow_id=flow_id)

    @staticmethod
    async def process_pending_jobs():
        """
        Worker that picks up 'pending' jobs from the DB and runs them.
        Handles FB_PUBLISH, YOUTUBE_PUBLISH, Dailymotion, etc.
        """
        from database import async_session
        from models import Job, JobStatus, JobType, SocialMediaAccount, AppSettings
        from services.facebook import FacebookService
        from services.youtube_bridge import YoutubeBridgeService
        from services.dailymotion_bridge import DailymotionBridgeService
        from services.x import XService
        from sqlalchemy import select
        
        async with async_session() as session:
            # Fetch pending jobs that are due
            now = datetime.utcnow()
            result = await session.execute(
                select(Job).where(
                    Job.status == JobStatus.PENDING,
                    Job.scheduled_at <= now
                )
            )
            jobs = result.scalars().all()
            
            if not jobs:
                return

            LoggerService.info(f"⚙️ Processing {len(jobs)} pending jobs...")

            for job in jobs:
                job.status = JobStatus.PROCESSING
                job.attempts += 1
                await session.commit()
                
                try:
                    import json
                    payload = json.loads(job.payload) if isinstance(job.payload, str) else job.payload
                    
                    # --- DISPATCHER ---
                    if job.type == JobType.FB_PUBLISH:
                        await ExecutionPipeline._execute_fb_publish(payload, session)
                    elif job.type == JobType.YOUTUBE_PUBLISH:
                         await ExecutionPipeline._execute_youtube_publish(payload, session)
                    elif job.type == JobType.DAILYMOTION_UPLOAD:
                         await ExecutionPipeline._execute_dailymotion_publish(payload, session)
                    elif job.type == JobType.X_PUBLISH:
                        await ExecutionPipeline._execute_x_publish(payload, session)
                    elif job.type == JobType.VIDEO_RENDER:
                        await ExecutionPipeline._execute_video_render(job, payload, session)
                    elif job.type == JobType.VIDEO_CHECK_STATUS:
                        await ExecutionPipeline._execute_video_status_check(job, payload, session)
                     # Add other types as needed
                    
                    job.status = JobStatus.SUCCESS
                    LoggerService.success(f"Job {job.id} [{job.type}] Completed")

                    # --- CLEANUP ---
                    # If mediaPath is a local file (e.g., static/uploads/...), delete it to save space
                    media_path = payload.get("mediaPath")
                    if media_path and not media_path.startswith("http") and "static/uploads" in media_path:
                         try:
                             import os
                             if os.path.exists(media_path):
                                 os.remove(media_path)
                                 LoggerService.info(f"🗑️ Deleted temp file: {media_path}")
                         except Exception as cleanup_err:
                             LoggerService.error(f"Failed to delete {media_path}: {cleanup_err}")
                    
                except Exception as e:
                    # If it's a "Wait more" signal, we might want to keep it pending?
                    # For now, mark failed so we see it.
                    job.status = JobStatus.FAILED
                    job.error = str(e)
                    LoggerService.error(f"Job {job.id} Failed: {e}")
                finally:
                    await session.commit()

    @staticmethod
    async def cleanup_stale_uploads():
        """
        Deletes files in static/uploads older than 24 hours.
        """
        import os
        import time
        
        upload_dir = "static/uploads"
        if not os.path.exists(upload_dir):
            return

        now = time.time()
        cutoff = now - (24 * 3600) # 24 hours ago
        
        count = 0
        for filename in os.listdir(upload_dir):
            file_path = os.path.join(upload_dir, filename)
            # Only delete files, not dirs (though uploads should be flat)
            if os.path.isfile(file_path):
                try:
                    mtime = os.path.getmtime(file_path)
                    if mtime < cutoff:
                        os.remove(file_path)
                        count += 1
                except Exception as e:
                    LoggerService.error(f"Error deleting stale file {filename}: {e}")
        
        if count > 0:
            LoggerService.info(f"🧹 Cleaned up {count} stale files from uploads.")

    # --- JOB EXECUTORS ---
    
    @staticmethod
    async def _execute_video_status_check(job, payload: dict, session):
        """
        Handles VIDEO_CHECK_STATUS.
        Polls NCA for completion, then queues Upload Jobs.
        """
        from services.ncakit import NcaKitService
        from models import AppSettings, FlowConfig, Job, JobType, JobStatus, GeneratedPost, SocialMediaAccount, SocialPlatform
        from sqlalchemy import select
        import asyncio
        import json
        import re
        
        video_job_id = payload.get("video_job_id")
        flow_id = payload.get("flow_id")
        module = payload.get("module", "short-video")
        
        LoggerService.info(f"🕵️ Checking Status for Video Job: {video_job_id} ({module})", flow_id=flow_id)
        
        # 1. Get Settings & NCA
        settings = (await session.execute(select(AppSettings))).scalars().first()
        nca_url = settings.nca_api_url if settings else "http://localhost:3000"
        nca = NcaKitService(nca_url)
        
        # 2. Check Status ONCE (Non-Blocking)
        status_data = await nca.get_status(video_job_id, module)
        status = status_data.get("status")
        
        # All valid "still working" statuses for various modules
        ONGOING_STATUSES = [
            "queued", "processing", "generating_audio", "generating_images", 
            "composing_video", "adding_text", "creating_video", "generating_image"
        ]

        if status in ONGOING_STATUSES:
             # RESCHEDULE: Job is still running. Free the worker and check back in 2 mins.
             LoggerService.info(f"🔄 [STATUS] Video still processing ({status}). Rescheduling check in 120s.", flow_id=flow_id)
             
             job.status = JobStatus.PENDING
             from datetime import timedelta
             job.scheduled_at = datetime.utcnow() + timedelta(seconds=120)
             job.attempts += 1 # Track how many times we checked
             
             session.add(job)
             # Note: Session commit happens in the caller (process_pending_jobs 'finally' block) or we can do it here.
             # process_pending_jobs does commit in finally. But we want to be sure.
             # preventing double-commit issue? process_pending_jobs commits at end of loop.
             # We can just return.
             return

        if status == "failed":
            err = status_data.get('error') or status_data.get('message') or "Unknown Error"
            raise Exception(f"Video Generation Failed: {err}")
        
        video_url = None
        if status in ["success", "ready", "completed"]:
            # SPECIAL LOGIC: For 'short-video', ALWAYS construct HF URL (ignore API return)
            if module == 'short-video':
                 # Usually video_job_id IS the nca_job_id in this context, but let's be robust
                 target_id = video_job_id
                 if job.result and job.result.get("nca_job_id"):
                     target_id = job.result.get("nca_job_id")
                 elif job.payload.get("nca_job_id"):
                     target_id = job.payload.get("nca_job_id")
                     
                 video_url = f"https://huggingface.co/datasets/robiul487/NCAkit/resolve/main/short_video/{target_id}.mp4?download=true"
                 LoggerService.info(f"🔗 Enforced HF Short Video URL: {video_url}", flow_id=flow_id)
            else:
                 # Standard Logic for other modules
                 video_url = status_data.get("video_url") or status_data.get("output") or status_data.get("videoUrl") or status_data.get("url")
            
                 if not video_url:
                      LoggerService.warn(f"⚠️ Standard keys missing. Searching deeply...", flow_id=flow_id)
                      str_dump = json.dumps(status_data)
                      urls = re.findall(r'https?://[^\s<>"]+|www\.[^\s<>"]+', str_dump)
                      video_candidates = [u for u in urls if u.endswith(('.mp4', '.mov', '.mkv')) or 'res.cloudinary' in u or 'blob:' in u]
                      if video_candidates:
                          video_url = video_candidates[0].strip('",')
                          LoggerService.info(f" Found hidden video URL: {video_url}", flow_id=flow_id)
            
            if not video_url and module == 'story-reel':
                 video_url = f"{nca_url}/api/story/story-reel/{video_job_id}"
                 LoggerService.info(f"🔗 Constructed Story Reel URL: {video_url}", flow_id=flow_id)
        
        if not video_url:
             # Should have been caught by "ongoing" check, but if status is weird:
             raise Exception(f"Unknown Status '{status}' and no URL found.")

        if not video_url:
            raise Exception("Video not ready after polling. Job failed (will retry).")
            
        LoggerService.success(f"✅ Video Ready: {video_url}", flow_id=flow_id)
        
        # 3. Create Upload Jobs (Chaining)
        # We need the FlowConfig to know target pages
        flow = await session.get(FlowConfig, flow_id)
        if not flow:
            LoggerService.error("Flow not found, cannot upload.", flow_id=flow_id)
            return

        # Prepare Content
        # Ideally, we should have saved the concept/script in payload to reuse as caption.
        # If missing, use a generic one.
        caption = f"{flow.name} #AI #Automation"
        
        # Save GeneratedPost
        post = GeneratedPost(
            content=caption,
            image_uri=video_url,
            original_source="AI_VIDEO",
            status="queued",
            flow_id=flow.id
        )
        session.add(post)
        
        target_ids = flow.target_page_ids or []
        
        # FIX: Ensure target_ids is a list (same as run_video_flow)
        if isinstance(target_ids, str):
            try:
                import json
                if target_ids.startswith("["):
                    target_ids = json.loads(target_ids)
                else:
                    target_ids = [target_ids]
            except:
                target_ids = [target_ids]
        for tid in target_ids:
            # Find Account
            acc_stmt = select(SocialMediaAccount).where(SocialMediaAccount.id == tid)
            acc = (await session.execute(acc_stmt)).scalars().first()
            
            if acc:
                job_type = JobType.FB_PUBLISH
                if acc.platform == SocialPlatform.X: job_type = JobType.X_PUBLISH
                elif acc.platform == SocialPlatform.YOUTUBE: job_type = JobType.YOUTUBE_PUBLISH
                elif acc.platform == SocialPlatform.DAILYMOTION: job_type = JobType.DAILYMOTION_UPLOAD
                
                new_job = Job(
                    type=job_type,
                    payload={
                        "accountId": acc.id,
                        "content": caption,
                        "videoUrl": video_url,
                        "mediaPath": video_url, # Key format compatibility
                        "videoType": "reel", # Force Reel
                        "videoTitle": f"AI Video {uuid.uuid4().hex[:4]}"
                    },
                    scheduled_at=datetime.utcnow(), # Run ASAP
                    status=JobStatus.PENDING
                )
                session.add(new_job)
                LoggerService.info(f"📦 Queued Upload for {acc.platform} ({acc.account_name})", flow_id=flow_id)

    @staticmethod
    async def _execute_fb_publish(payload: dict, session):
        from models import SocialMediaAccount, AppSettings
        from services.facebook import FacebookService
        from sqlalchemy import select

        acc_id = payload.get("accountId")
        caption = payload.get("caption")
        media_path = payload.get("mediaPath")
        title = payload.get("videoTitle")
        v_type = payload.get("videoType")

        # SANITIZATION: Fix broken NCA proxy URLs (for retries of old jobs)
        if media_path and "api/video/short-video" in media_path:
             try:
                 # Extract Job ID from URL: .../api/video/short-video/{job_id}
                 job_id = media_path.split("/")[-1]
                 # Remove query params if any
                 if "?" in job_id: job_id = job_id.split("?")[0]
                 
                 media_path = f"https://huggingface.co/datasets/robiul487/NCAkit/resolve/main/short_video/{job_id}.mp4?download=true"
                 LoggerService.warn(f"⚠️ Sanitized FB Upload URL to HF: {media_path}", flow_id=None)
             except:
                 pass

        # SAFETY: Truncate title for all FB uploads
        if title and len(title) > 95:
            title = title[:95]

        # Reuse session passed from worker
        acc = await session.get(SocialMediaAccount, acc_id)
        if not acc:
            # Try searching by page_id
            statement = select(SocialMediaAccount).where(SocialMediaAccount.page_id == str(acc_id))
            results = await session.execute(statement)
            acc = results.scalars().first()

        token = None
        if acc:
            token = acc.access_token
        else:
            settings = (await session.execute(select(AppSettings))).scalars().first()
            if settings and settings.fb_page_id == acc_id:
                token = settings.fb_access_token
        
        if not token:
            raise Exception(f"No token found for Account {acc_id}")
            
        if v_type == 'reel':
            await FacebookService.upload_reel(acc_id, token, media_path, caption)
        elif media_path and media_path.lower().endswith(('.mp4', '.mov', '.avi', '.mkv')):
            await FacebookService.upload_video(acc_id, token, media_path, title, caption)
        elif media_path:
            await FacebookService.upload_photo(acc_id, token, media_path, caption)
        else:
            # Text Only
            await FacebookService.publish_text(acc_id, token, caption)

    @staticmethod
    async def _execute_youtube_publish(payload: dict, session):
        from models import SocialMediaAccount
        from services.youtube import YouTubeService
        
        acc_id = payload.get("accountId")
        title = payload.get("videoTitle") or payload.get("title") or "Untitled Video"
        
        # SAFETY: YouTube title limit is 100 chars
        if title and len(title) > 95:
             title = title[:95]

        description = payload.get("description") or payload.get("caption") or ""
        media_path = payload.get("mediaPath")
        
        # SANITIZATION: Fix broken NCA proxy URLs (for retries of old jobs)
        if media_path and "api/video/short-video" in media_path:
             try:
                 # Extract Job ID from URL: .../api/video/short-video/{job_id}
                 job_id = media_path.split("/")[-1]
                 # Remove query params if any
                 if "?" in job_id: job_id = job_id.split("?")[0]
                 
                 media_path = f"https://huggingface.co/datasets/robiul487/NCAkit/resolve/main/short_video/{job_id}.mp4?download=true"
                 LoggerService.warn(f"⚠️ Sanitized YouTube Upload URL to HF: {media_path}", flow_id=None)
             except:
                 pass

        tags = payload.get("tags", [])
        tags = payload.get("tags", [])
        privacy = payload.get("privacy", "public")  # Default to public per user feedback
        
        if not media_path:
            raise Exception("No video file path provided for YouTube upload")
        
        acc = await session.get(SocialMediaAccount, acc_id)
        if not acc:
            raise Exception(f"YouTube account not found: {acc_id}")
        
        if not acc.client_id or not acc.client_secret or not acc.refresh_token:
            raise Exception(f"YouTube account {acc.account_name} missing OAuth credentials")
        
        LoggerService.info(f"🎬 Uploading to YouTube: {acc.account_name} ({acc.handle})")
        LoggerService.info(f"   Title: {title}")
        LoggerService.info(f"   Video: {media_path}")
        
        try:
            # Use YouTubeService with refresh token (auto-refreshes access token)
            video_id = await YouTubeService.upload_video(
                client_id=acc.client_id,
                client_secret=acc.client_secret,
                refresh_token=acc.refresh_token,
                file_path_or_url=media_path,
                metadata={
                    "title": title,
                    "description": description,
                    "tags": tags if isinstance(tags, list) else [],
                    "privacy": privacy,
                    "categoryId": "22"  # People & Blogs
                }
            )
            
            LoggerService.success(f"✅ YouTube Upload Successful! Video ID: {video_id}")
            LoggerService.info(f"   URL: https://youtu.be/{video_id}")
            return video_id
            
        except Exception as upload_err:
            error_msg = str(upload_err)
            if "uploadLimitExceeded" in error_msg:
                LoggerService.error(f"❌ YouTube Upload Quota Exceeded for {acc.account_name}")
                raise Exception("YouTube Usage Limit Exceeded (Quota). Retry in 24 hours.")
            
            LoggerService.error(f"❌ YouTube Upload Failed: {upload_err}")
            raise Exception(f"YouTube upload failed: {upload_err}")

    @staticmethod
    async def _execute_dailymotion_publish(payload: dict, session):
        from models import SocialMediaAccount
        from services.dailymotion_bridge import DailymotionBridgeService
        
        acc_id = payload.get("accountId")
        title = payload.get("videoTitle")
        description = payload.get("caption")
        media_path = payload.get("mediaPath")
        
        acc = await session.get(SocialMediaAccount, acc_id)
        if not acc: raise Exception("Account not found")
        
        dm = DailymotionBridgeService()
        upload_url = await dm.get_upload_url(acc.access_token)
        vid_url = await dm.upload_file(upload_url, media_path)
        await dm.create_video(acc.access_token, vid_url, {"title": title, "description": description, "published": True})

    @staticmethod
    async def _execute_video_render(job: Job, payload: dict, session):
        """Processes a VIDEO_RENDER job by submitting to NCAKit and polling for results."""
        from services.ncakit import NcaKitService
        from models import JobStatus, AppSettings
        from sqlalchemy import select
        import asyncio

        # 1. Resolve NCA URL
        settings = (await session.execute(select(AppSettings))).scalars().first()
        nca_url = settings.nca_api_url if settings else "http://localhost:3000"
        nca = NcaKitService(nca_url)
        
        video_type = payload.get("video_type", "short-video")
        LoggerService.info(f"🎬 Submitting {video_type} to NCAKit: {nca_url}")
        
        nca_job_id = None
        try:
            if video_type == "story-reel":
                res = await nca.create_story_reel(
                    script=payload.get("script", ""),
                    image_style=payload.get("image_style", "semi-realistic"),
                    voice=payload.get("voice", "af_heart")
                )
                nca_job_id = res.get("job_id")
            
            elif video_type == "short-video":
                res = await nca.create_short_video(
                    scenes=payload.get("scenes", []),
                    config=payload.get("config", {})
                )
                nca_job_id = res.get("videoId")
                
            elif video_type == "fact-image":
                res = await nca.create_fact_image(
                    model=payload.get("model", "nvidia"),
                    image_prompt=payload.get("image_prompt", ""),
                    fact_text=payload.get("fact_text", ""),
                    fact_heading=payload.get("fact_heading", ""),
                    duration=payload.get("duration", 5)
                )
                nca_job_id = res.get("job_id")
                
            elif video_type == "quiz":
                res = await nca.create_quiz_reel(
                    quizzes=payload.get("quizzes", []),
                    voice=payload.get("voice", "af_heart")
                )
                nca_job_id = res.get("job_id")
                
            elif video_type == "text-story":
                res = await nca.create_text_story(
                    messages=payload.get("messages", []),
                    person_a_name=payload.get("person_a_name", "You"),
                    person_b_name=payload.get("person_b_name", "Friend"),
                    voice_a=payload.get("voice_a", "af_heart"),
                    voice_b=payload.get("voice_b", "am_fenrir"),
                    ending_text=payload.get("ending_text")
                )
                nca_job_id = res.get("job_id")

            if not nca_job_id:
                raise Exception(f"NCAKit returned no ID for {video_type}")

            LoggerService.info(f"✅ Submitted to NCAKit: {nca_job_id}. Transitioning to Polling...", flow_id=job.flow_id)
            
            # Refactor: Non-Blocking Polling
            # Instead of looping here, we update the Job to type VIDEO_CHECK_STATUS
            # and schedule it for 30 seconds later.
            
            job.type = JobType.VIDEO_CHECK_STATUS
            job.payload = {
                **payload, 
                "video_job_id": nca_job_id,
                "flow_id": job.flow_id,
                "module": video_type
            }
            job.status = JobStatus.PENDING # Ready to be picked up again
            job.scheduled_at = datetime.utcnow() + timedelta(seconds=30)
            job.attempts = 0 # Reset attempts for the new phase
            
            session.add(job)
            await session.commit()
            
            LoggerService.info(f"🔄 Job {job.id} transitioned to VIDEO_CHECK_STATUS. Next check in 30s.", flow_id=job.flow_id)

            # 3. Finalize Job (It will be picked up by status check)
            # job.status = JobStatus.SUCCESS <-- DON'T mark success yet, it's pending check
            # We already saved it as PENDING above.
            return

        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            LoggerService.error(f"❌ Video Job Failed: {e}")
            raise e

    @staticmethod
    async def _execute_x_publish(payload: dict, session):
        from models import SocialMediaAccount
        from services.x import XService
        acc_id = payload.get("accountId")
        text = payload.get("caption")
        media_path = payload.get("mediaPath")
        
        acc = await session.get(SocialMediaAccount, acc_id)
        if not acc: raise Exception("Account not found")
        
        x = XService()
        # Stubbing X upload for now until XService is verified backend-side
        # media_id = await x.upload_video(acc, media_path) 
        # await x.post_tweet(acc, text, media_ids=[media_id] if media_id else [])
        LoggerService.info(f"Simulating X Upload to {acc.account_name}")
