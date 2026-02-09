import asyncio
import uuid
from datetime import datetime, timedelta
from sqlmodel import select
from models import FlowConfig, Job, JobType, JobStatus, GeneratedPost, AppSettings, SocialPlatform, SocialMediaAccount
from services.rss import RSSService
from services.ai import ContentService
from services.facebook import FacebookService
from services.weather import WeatherService
from services.ncakit import NcaKitService # Added ncakit import
from services.notification_service import NotificationService

class AssistantService:
    @classmethod
    async def execute_flow(cls, session, flow: FlowConfig, job: Job = None):
        """Main entry point for executing an assistant's automation cycle"""
        cls.log(job, f"🤖 Starting execution cycle for '{flow.name}'...")
        
        try:
            if flow.source_type == "RSS":
                await cls.process_rss_flow(session, flow, job)
            elif flow.source_type == "AI_TOPIC":
                await cls.process_ai_topic_flow(session, flow, job)
            elif flow.source_type == "IMAGE_CAPTION":
                await cls.process_image_caption_flow(session, flow, job)
            elif flow.source_type == "VIDEO_AUTOMATION":
                await cls.process_video_flow(session, flow, job)
            elif flow.source_type == "WEATHER_POST":
                await cls.process_weather_flow(session, flow, job)
            
            # Update last run
            flow.last_run_at = datetime.utcnow()
            session.add(flow)
            cls.log(job, "✅ Execution cycle completed successfully.")
            
            # 1:1 Parity Notification
            await NotificationService.send_success(session, flow.name, "Automation cycle completed successfully. 🚀")
            
        except Exception as e:
            cls.log(job, f"❌ Error: {str(e)}")
            raise e

    @staticmethod
    def log(job: Job, message: str):
        """Helper to print and save logs to the Job record"""
        print(message)
        if job:
            timestamp = datetime.utcnow().strftime("%H:%M:%S")
            job.execution_logs = job.execution_logs + [f"[{timestamp}] {message}"]

    @classmethod
    async def process_rss_flow(cls, session, flow: FlowConfig, job: Job = None):
        """Handles RSS-based assistants: Aggregates feeds, rewrites with AI, and queues posts"""
        all_items = []
        cls.log(job, f"📡 Fetching RSS feeds for '{flow.name}'...")
        
        for feed in flow.rss_feeds:
            url = feed.get("url")
            if url:
                try:
                    items = RSSService.fetch_feed(url)
                    all_items.extend(items[:5]) 
                    cls.log(job, f"Fetched {len(items[:5])} items from {url}")
                except Exception as e:
                    cls.log(job, f"Warning: Failed to fetch {url}: {e}")
        
        new_items = []
        for item in all_items:
            existing = (await session.execute(select(GeneratedPost).where(GeneratedPost.original_source == item.link))).scalars().first()
            if not existing:
                new_items.append(item)
        
        cls.log(job, f"Found {len(new_items)} new items to process.")
        
        for idx, item in enumerate(new_items):
            content = f"{item.title}\n\n{item.description}"
            if flow.rewrite_policy == "AI_REWRITE":
                cls.log(job, f"Applying AI Rewrite to: {item.title[:30]}...")
                content = await cls.apply_ai_rewrite(flow, session, content)
            
            final_text = cls.apply_formatting(flow, content)
            await cls.queue_post(session, flow, final_text, item.link, delay_mins=idx * 15, job=job)

    @classmethod
    async def process_ai_topic_flow(cls, session, flow: FlowConfig, job: Job = None):
        """Handles AI Topic assistants: Generates niche-specific content from structured prompts"""
        prompt = flow.ai_topic_prompt or "Generate a viral post about technology news."
        cls.log(job, f"🧠 Generating content for topic: {flow.name}...")
        
        content = await cls.apply_ai_rewrite(flow, session, prompt)
        final_text = cls.apply_formatting(flow, content)
        
        await cls.queue_post(session, flow, final_text, "AI_TOPIC", job=job)

    @classmethod
    async def process_weather_flow(cls, session, flow: FlowConfig, job: Job = None):
        """Mirroring mobile's handleWeatherAutomationFlow"""
        cfg = flow.weather_config
        if not cfg: 
            cls.log(job, "⚠️ Missing weather config. Skipping.")
            return
        
        country_code = cfg.get("countryCode", "BD")
        template = cfg.get("reportTemplate", "DIVISIONAL_TABLE")
        cls.log(job, f"🌤️ Generating Weather Report ({template}) for {country_code}...")
        
        content = ""
        if template == "DIVISIONAL_TABLE":
            content = await WeatherService.generate_divisional_weather_table(country_code)
        elif template == "FLASH_UPDATE":
            content = await WeatherService.generate_flash_update(country_code)
        elif template == "VIRAL_ALERT":
            result = await WeatherService.get_viral_weather_update(country_code)
            if result and result["alert"] and result["alert"]["viral_potential"] >= 7:
                content = await WeatherService.generate_flash_update(country_code)
            else:
                cls.log(job, "No viral weather alert found. Skipping.")
                return
                
        if content:
            await cls.queue_post(session, flow, content, "WEATHER", job=job)

    @classmethod
    async def process_image_caption_flow(cls, session, flow: FlowConfig, job: Job = None):
        """Mirroring mobile's handleImageCaptionFlow"""
        cfg = flow.image_caption_config
        if not cfg: 
            cls.log(job, "⚠️ Missing image caption config. Skipping.")
            return
        
        cls.log(job, "🎨 Starting Image Caption Flow...")
        
        # Phase 1: Image Generation
        image_prompt_request = f"SYSTEM: {cfg.get('systemPrompt')}\nTOPIC: {cfg.get('niche')}\nSTYLE: {cfg.get('imageStyle')}\nTASK: Detailed image prompt."
        cls.log(job, "Generating image prompt...")
        generated_image_prompt = await cls.apply_ai_rewrite(flow, session, image_prompt_request)
        
        app_settings = (await session.execute(select(AppSettings))).scalars().first()
        config_id = flow.image_gen_config_id or flow.ai_config_id
        img_cfg = next((c for c in app_settings.image_gen_configs if c["id"] == config_id), app_settings.image_gen_configs[0] if app_settings.image_gen_configs else None)
        
        if not img_cfg: raise Exception("No Image Generation Config found")
        
        provider = img_cfg["provider"]
        model = img_cfg.get("model")
        cls.log(job, f"Generating image with {provider} ({model or 'default'})...")
        image_bytes = await ContentService.generate_image(provider, img_cfg["apiKey"], generated_image_prompt, img_cfg.get("workerUrl"), model=model)
        
        image_path = f"static/uploads/{uuid.uuid4()}.png"
        with open(image_path, "wb") as f:
            f.write(image_bytes)
        cls.log(job, f"Image generated and saved: {image_path}")
            
        # Phase 2: Caption
        caption = ""
        if cfg.get("generateCaption"):
            cls.log(job, "Generating caption...")
            caption_req = f"IMAGE PROMPT: {generated_image_prompt}\nTASK: Write a Facebook post caption."
            caption = await cls.apply_ai_rewrite(flow, session, caption_req)
            
        await cls.queue_post(session, flow, caption, "IMAGE_CAPTION", image_url=image_path, job=job)

    @classmethod
    async def process_video_flow(cls, session, flow: FlowConfig, job: Job = None):
        """Mirroring mobile's handleVideoAutomationFlow"""
        cfg = flow.video_automation_config
        if not cfg: 
            cls.log(job, "⚠️ Missing video config. Skipping.")
            return
        
        module = cfg.get("videoModule", "story-reel")
        niche = cfg.get("videoNiche", "General")
        cls.log(job, f"🎬 Starting Video Flow: {module} ({niche})...")
        
        # 1. Generate Script
        cls.log(job, "Generating video script...")
        script_prompt = f"TOPIC: {niche}\nDETAIL: {cfg.get('videoNicheDetails')}\nTASK: Generate video script."
        script = await cls.apply_ai_rewrite(flow, session, script_prompt)
        
        # 2. Call NCAKit
        app_settings = (await session.execute(select(AppSettings))).scalars().first()
        if not app_settings.nca_api_url: raise Exception("NCA API URL not configured")
        
        nca = NcaKitService(app_settings.nca_api_url)
        
        cls.log(job, f"Requesting {module} from NCAKit...")
        if module == "story-reel":
            result = await nca.create_story_reel(script, cfg.get("videoStyle", "semi-realistic"), cfg.get("videoVoice", "af_heart"))
        elif module == "fact-image":
            # Support dynamic image provider for fact-image
            img_provider = "nvidia" # Default
            img_config_id = flow.image_gen_config_id
            
            if img_config_id:
                # If it's a known provider name (legacy/simple selection)
                if img_config_id in ["nvidia", "cloudflare", "pexels"]:
                    img_provider = img_config_id
                else:
                    # Look up from configs
                    ai_cfg = next((c for c in app_settings.image_gen_configs if c["id"] == img_config_id), None)
                    if ai_cfg:
                        img_provider = ai_cfg.get("provider", "nvidia").lower()
            
            cls.log(job, f"Requesting {module} with image provider: {img_provider}...")
            result = await nca.create_fact_image(img_provider, script, "Fact Text", "Heading")
        
        if result and "job_id" in result:
             job_id = result["job_id"]
             cls.log(job, f"NCA Job Created: {job_id}. Polling job queued.")
             status_job = Job(
                 type=JobType.VIDEO_CHECK_STATUS,
                 payload={"video_job_id": job_id, "flow_id": flow.id, "module": module},
                 scheduled_at=datetime.utcnow() + timedelta(minutes=1),
                 status=JobStatus.PENDING
             )
             session.add(status_job)

    @classmethod
    async def apply_ai_rewrite(cls, flow: FlowConfig, session, text: str) -> str:
        """Helper to call AI based on Assistant configuration with multi-provider support"""
        app_settings = (await session.execute(select(AppSettings))).scalars().first()
        
        api_key = app_settings.gemini_api_key
        provider = "Gemini"
        model = "gemini-1.5-flash"
        
        if flow.ai_config_id:
            ai_cfg = next((c for c in app_settings.ai_configs if c["id"] == flow.ai_config_id), None)
            if ai_cfg:
                api_key = ai_cfg["apiKey"]
                provider = ai_cfg["provider"]
                model = ai_cfg.get("model", model)
        
        if provider == "Gemini":
            return ContentService.generate_with_gemini(api_key, text, model)
        elif provider == "Groq":
            return ContentService.generate_with_groq(api_key, text, model)
        elif provider == "OpenRouter":
            return ContentService.generate_with_openrouter(api_key, text, model)
            
        return text

    @staticmethod
    def apply_formatting(flow: FlowConfig, text: str) -> str:
        """Applies template and hashtag strategies"""
        final = text
        if flow.post_template:
            final = flow.post_template.replace("[CONTENT]", text)
        
        if flow.hashtag_strategy == "AUTO":
             final += "\n\n#AI #Automation #Trending"
        elif flow.hashtag_strategy == "FIXED" and flow.custom_ai_prompt: 
             final += f"\n\n{flow.custom_ai_prompt}"
             
        return final

    @staticmethod
    async def queue_post(session, flow: FlowConfig, content: str, source: str, image_url=None, video_url=None, delay_mins=0, job: Job = None):
        """Creates a Draft Post and Publish Jobs for ALL target accounts (FB, X, YT, DM)"""
        AssistantService.log(job, f"📦 Queuing post to {len(flow.target_page_ids or [])} accounts...")
        
        post = GeneratedPost(
            content=content,
            image_uri=image_url or video_url, 
            original_source=source,
            status="queued",
            flow_id=flow.id
        )
        session.add(post)
        
        target_ids = flow.target_page_ids or []
        for tid in target_ids:
            account = (await session.execute(select(SocialMediaAccount).where(SocialMediaAccount.id == tid))).scalars().first()
            
            if not account:
                AssistantService.log(job, f"⚠️ Warning: Target Account ID {tid} not found. Skipping.")
                continue

            if account:
                job_type = JobType.FB_PUBLISH
                if account.platform == SocialPlatform.X:
                    job_type = JobType.X_PUBLISH
                elif account.platform == SocialPlatform.YOUTUBE:
                    job_type = JobType.YOUTUBE_PUBLISH
                elif account.platform == SocialPlatform.DAILYMOTION:
                    job_type = JobType.DAILYMOTION_UPLOAD
                
                new_job = Job(
                    type=job_type,
                    payload={
                        "accountId": account.id,
                        "content": content,
                        "imageUri": image_url,
                        "videoUrl": video_url,
                        "pageId": account.page_id 
                    },
                    scheduled_at=datetime.utcnow() + timedelta(minutes=delay_mins),
                    status=JobStatus.PENDING
                )
                session.add(new_job)
        
        await session.commit()
