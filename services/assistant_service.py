import asyncio
import uuid
import json
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
            if flow.source_type == "VIDEO_AUTOMATION":
                cls.log(job, "✅ Video Flow Initialized: Topic/Script generated and Rendering job queued.")
            else:
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
        """Mirroring mobile's handleVideoAutomationFlow with dynamic concepts"""
        cfg = flow.video_automation_config
        if not cfg: 
            cls.log(job, "⚠️ Missing video config. Skipping.")
            return
        
        module = cfg.get("module", "story-reel")
        niche = cfg.get("niche", "General")
        niche_details = cfg.get("nicheDetails", "")
        cls.log(job, f"🎬 Starting Video Flow: {module} ({niche})...")
        
        # 0. AI Config Resolution
        app_settings = (await session.execute(select(AppSettings))).scalars().first()
        ai_config_id = flow.ai_config_id
        ai_cfg = next((c for c in app_settings.ai_configs if c["id"] == ai_config_id), None)
        if not ai_cfg:
            ai_cfg = {"provider": "Gemini", "apiKey": app_settings.gemini_api_key, "model": "gemini-2.0-flash"}
        
        from services.video_ai import VideoAiService
        
        # 1. Generate Topic (Concept)
        cls.log(job, "🧠 Generating viral topic...")
        topic_template = cfg.get("topicSystemPrompt") # Matches FlowBuilderScreen.tsx
        topic = await VideoAiService.generate_concept(ai_cfg, niche, niche_details, topic_template)
        cls.log(job, f"Topic Generated: {topic}")

        # 2. Generate Script/Content based on Module
        cls.log(job, f"📝 Generating {module} content...")
        custom_prompt = cfg.get("scriptSystemPrompt") # Matches FlowBuilderScreen.tsx
        
        result_data = None
        if module == "story-reel":
            style = cfg.get("style", "Cinematic")
            result_data = await VideoAiService.generate_story_reel_content(ai_cfg, topic, style, niche, niche_details, custom_prompt)
            script = result_data.get("script", "")
        elif module == "short-video":
            result_data = await VideoAiService.generate_short_video_content(ai_cfg, topic, niche, niche_details, custom_prompt)
            script = json.dumps(result_data) # Logged for history
        elif module == "fact-image":
            result_data = await VideoAiService.generate_fact_image_content(ai_cfg, topic, niche, niche_details, custom_prompt)
            script = result_data.get("fact_text", "")
        elif module == "quiz":
            count = cfg.get("quizCount", 5)
            result_data = await VideoAiService.generate_quiz_content(ai_cfg, topic, count, niche, niche_details, custom_prompt)
            script = json.dumps(result_data)
        
        if not result_data:
            raise Exception(f"Failed to generate content for {module}")

        # 3. Call NCAKit
        if not app_settings.nca_api_url: raise Exception("NCA API URL not configured")
        nca = NcaKitService(app_settings.nca_api_url)
        
        cls.log(job, f"🚀 Sending to NCAKit ({module})...")
        result = None
        if module == "story-reel":
            result = await nca.create_story_reel(result_data.get("script", ""), cfg.get("style", "semi-realistic"), cfg.get("voice", "af_heart"))
        elif module == "short-video":
            nca_cfg = {
                "voice": cfg.get("voice", "af_heart"),
                "music": cfg.get("music", "chill"),
                "style": cfg.get("style", "semi-realistic")
            }
            result = await nca.create_short_video(result_data.get("scenes", []), nca_cfg)
        elif module == "fact-image":
            img_provider = "nvidia" 
            img_config_id = flow.image_gen_config_id
            if img_config_id:
                if img_config_id in ["nvidia", "cloudflare", "pexels"]:
                    img_provider = img_config_id
                else:
                    ai_config_lookup = next((c for c in app_settings.image_gen_configs if c["id"] == img_config_id), None)
                    if ai_config_lookup:
                        img_provider = ai_config_lookup.get("provider", "nvidia").lower()
            
            result = await nca.create_fact_image(
                img_provider, 
                result_data.get("image_prompt", ""), 
                result_data.get("fact_text", ""), 
                result_data.get("fact_heading", "DID YOU KNOW?")
            )
        elif module == "quiz":
            result = await nca.create_quiz_reel(result_data.get("quizzes", []), cfg.get("voice", "af_heart"))
        
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
            return await ContentService.generate_with_gemini(api_key, text, model)
        elif provider == "Groq":
            return await ContentService.generate_with_groq(api_key, text, model)
        elif provider == "OpenRouter":
            return await ContentService.generate_with_openrouter(api_key, text, model)
            
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
            # Find Account (Robust lookup by internal ID or Page ID)
            from sqlalchemy import or_
            stmt = select(SocialMediaAccount).where(
                or_(
                    SocialMediaAccount.id == tid,
                    SocialMediaAccount.page_id == str(tid)
                )
            )
            account = (await session.execute(stmt)).scalars().first()
            
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
