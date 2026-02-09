import unittest
from unittest.mock import AsyncMock, patch, MagicMock
from datetime import datetime
from sqlmodel import SQLModel, select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
import asyncio

# Adjust path to import backend modules
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models import Job, JobType, JobStatus, AppSettings, FlowConfig, SocialMediaAccount, SocialPlatform
from services.scheduler import SchedulerService
from models import GeneratedPost # Make sure this is imported to avoid "from models import GeneratedPost" error inside function

# Mock Data
MOCK_NCA_JOB_ID = "nca_12345"
MOCK_VIDEO_URL = "http://nca.com/video.mp4"

class TestVideoFlow(unittest.IsolatedAsyncioTestCase):
    
    async def asyncSetUp(self):
        # Setup In-Memory DB
        self.engine = create_async_engine("sqlite+aiosqlite:///:memory:")
        async with self.engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)
        
        self.AsyncSession = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

    async def asyncTearDown(self):
        await self.engine.dispose()

    async def test_video_render_flow(self):
        """
        Verifies the End-to-End flow:
        1. VIDEO_RENDER Job -> Calls NCA -> Creates VIDEO_CHECK_STATUS Job
        2. VIDEO_CHECK_STATUS Job -> Checks NCA -> Creates Publish Job
        """
        async with self.AsyncSession() as session:
            # 1. Setup Data
            settings = AppSettings(
                nca_api_url="http://nca.api",
                gemini_api_key="fake_key",
                fb_page_id="123",
                fb_access_token="abc"
            )
            session.add(settings)
            
            account = SocialMediaAccount(
                id="acc_1", 
                platform=SocialPlatform.FACEBOOK, 
                page_id="123", 
                account_name="Test Account",
                handle="@testpage",
                access_token="token"
            )
            session.add(account)
            
            flow = FlowConfig(
                name="Test Flow", 
                source_type="VIDEO_AUTOMATION",
                target_page_ids=["acc_1"],
                video_automation_config={"module": "story-reel", "niche": "Tech"}
            )
            session.add(flow)
            await session.commit()
            await session.refresh(flow)
            
            # 2. Create Initial Job (VIDEO_RENDER)
            render_job = Job(
                type=JobType.VIDEO_RENDER,
                payload={
                    "flowId": flow.id,
                    "prompt": "Test Concept",
                    "video_type": "story-reel"
                },
                status=JobStatus.PENDING,
                scheduled_at=datetime.utcnow()
            )
            session.add(render_job)
            await session.commit()
            
            # 3. MOCK External Services
            with patch("services.ncakit.NcaKitService") as MockNcaClass, \
                 patch("services.video_ai.VideoAiService") as MockVideoAi:
                
                # Mock NCA Service
                nca_instance = MockNcaClass.return_value
                nca_instance.create_story_reel = AsyncMock(return_value={"job_id": MOCK_NCA_JOB_ID})
                nca_instance.get_status = AsyncMock(return_value={
                    "status": "success", 
                    "video_url": MOCK_VIDEO_URL,
                    "caption": "Test Caption"
                })
                
                # Mock Video AI (Skip generation logic)
                MockVideoAi.generate_story_reel_content.return_value = {
                    "script": "Script", 
                    "image_style": "Style"
                }
                
                # --- EXECUTE STEP 1: VIDEO_RENDER ---
                print(">>> Executing VIDEO_RENDER Job...")
                await SchedulerService.execute_job(session, render_job)
                
                # Verify Job Status
                await session.refresh(render_job)
                assert render_job.status == JobStatus.SUCCESS
                
                # Verify NCA Call
                nca_instance.create_story_reel.assert_called_once()
                
                # Verify Check Status Job Created
                check_jobs = (await session.execute(select(Job).where(Job.type == JobType.VIDEO_CHECK_STATUS))).scalars().all()
                assert len(check_jobs) == 1
                check_job = check_jobs[0]
                assert check_job.payload["video_job_id"] == MOCK_NCA_JOB_ID
                assert check_job.status == JobStatus.PENDING
                
                # --- EXECUTE STEP 2: VIDEO_CHECK_STATUS ---
                print(">>> Executing VIDEO_CHECK_STATUS Job...")
                await SchedulerService.execute_job(session, check_job)
                
                # Verify Check Job Status
                await session.refresh(check_job)
                assert check_job.status == JobStatus.SUCCESS
                
                # Verify NCA Status Check
                nca_instance.get_status.assert_called_with(MOCK_NCA_JOB_ID, "story-reel")
                
                # Verify Publish Job Created (Queued)
                posts = (await session.execute(select(GeneratedPost))).scalars().all()
                assert len(posts) == 1
                assert posts[0].image_uri == MOCK_VIDEO_URL # video_url is stored in image_uri/video_url field logic
                
                publish_jobs = (await session.execute(select(Job).where(Job.type == JobType.FB_PUBLISH))).scalars().all()
                assert len(publish_jobs) == 1
                pub_job = publish_jobs[0]
                assert pub_job.payload["videoUrl"] == MOCK_VIDEO_URL
                assert pub_job.payload["accountId"] == "acc_1"
                
                print(">>> Test Completed Successfully!")

if __name__ == "__main__":
    unittest.main()
