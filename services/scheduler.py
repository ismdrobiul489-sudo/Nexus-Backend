from pytz import utc
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from .execution_pipeline import ExecutionPipeline
from .logger_service import LoggerService
from models.sync import SyncAssistant

import logging
from datetime import datetime, timedelta
import asyncio
import os

logger = logging.getLogger(__name__)

class SchedulerService:
    _scheduler = None
    
    @classmethod
    def get_scheduler(cls):
        return cls._scheduler
    
    @classmethod
    def start(cls):
        # 0. Check Lock File to prevent double-scheduler (e.g. Reloader or Multiple Terminals)
        lock_dir = "/app/data" if os.path.exists("/app/data") else "."
        lock_file = os.path.join(lock_dir, "scheduler.lock")
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    old_pid = int(f.read().strip())
                
                # Check if process is still running
                try:
                    os.kill(old_pid, 0) # Check if alive
                    
                    # FORCE ACTIVE STRATEGY (Aggressive):
                    # User requested NO WAITING. We immediately take over.
                    LoggerService.warn(f"⚠️ Scheduler locked by PID {old_pid}. Stealing lock IMMEDIATELY.")
                    
                    # Optional: We could try to kill the old process here, but it might be dangerous.
                    # Given 'uvicorn --reload', the old process should be dying anyway.
                    # We proceed to overwrite the lock below.

                except OSError:
                    # Process dead, stale lock
                    LoggerService.info(f"Removing stale scheduler lock from PID {old_pid}")
                    try:
                        os.remove(lock_file)
                    except FileNotFoundError:
                        pass
            except Exception:
                # Corrupt lock file
                pass
        
        # Write Lock
        try:
            with open(lock_file, 'w') as f:
                f.write(str(os.getpid()))
        except Exception as e:
            LoggerService.error(f"Failed to write scheduler lock: {e}")

        if cls._scheduler is None:
            # Allow override for cloud persistence (e.g. /data/jobs.sqlite)
            jobs_db_url = os.getenv("JOBS_DB_URL", f"sqlite:///{os.path.abspath('jobs.sqlite')}")
            jobstores = {
                'default': SQLAlchemyJobStore(url=jobs_db_url)
            }
            # misfire_grace_time=3600: If PC is off, run jobs missed within last 1 hour
            cls._scheduler = AsyncIOScheduler(jobstores=jobstores, job_defaults={'misfire_grace_time': 3600}, timezone=utc)
            
            # --- SYSTEM JOBS ---
            # 1. Process Pending Manual Jobs (Every 1 min)
            cls._scheduler.add_job(
                ExecutionPipeline.process_pending_jobs,
                trigger=IntervalTrigger(minutes=1),
                id='system_job_processor',
                name='System: Process Pending Jobs',
                replace_existing=True,
                coalesce=True
            )

            # 2. Daily Cleanup (Every 24 hours) - Remove stale uploads
            cls._scheduler.add_job(
                ExecutionPipeline.cleanup_stale_uploads,
                trigger=IntervalTrigger(hours=24),
                id='system_cleanup',
                name='System: Cleanup Stale Uploads',
                replace_existing=True,
                coalesce=True
            )
            
            cls._scheduler.start()
            LoggerService.info(f"✅ APScheduler Started in PID {os.getpid()}")
            
    @classmethod
    def stop(cls):
        if cls._scheduler:
            cls._scheduler.shutdown()
        
        # Remove Lock
        lock_dir = "/app/data" if os.path.exists("/app/data") else "."
        lock_file = os.path.join(lock_dir, "scheduler.lock")
        if os.path.exists(lock_file):
            try:
                with open(lock_file, 'r') as f:
                    pid = int(f.read().strip())
                if pid == os.getpid():
                    os.remove(lock_file)
            except:
                pass
            
    @classmethod
    async def execute_wrapper(cls, assistant_config: dict, retry_count: int = 0):
        """
        Robust Wrapper: Handles Execution + Auto-Retry on Failure.
        """
        flow_id = assistant_config.get("id")
        flow_name = assistant_config.get("name")
        
        try:
            await ExecutionPipeline.execute_flow(assistant_config)
            
        except Exception as e:
            LoggerService.error(f"⚠️ Job Failed: {flow_name} (Attempt {retry_count+1}/4)", flow_id=flow_id, error=e)
            
            # Retry Logic (Max 3 retries)
            if retry_count < 3:
                delay_minutes = 5 * (retry_count + 1) # Progressive delay: 5, 10, 15
                run_date = datetime.now() + timedelta(minutes=delay_minutes)
                
                cls._scheduler.add_job(
                    cls.execute_wrapper,
                    trigger='date',
                    run_date=run_date,
                    args=[assistant_config, retry_count + 1],
                    id=f"{flow_id}_retry_{retry_count}_{int(datetime.now().timestamp())}",
                    name=f"Retry: {flow_name} ({retry_count+1})",
                    misfire_grace_time=3600
                )
                LoggerService.info(f"🔁 Scheduled Retry #{retry_count+1} for {flow_name} in {delay_minutes}m", flow_id=flow_id)
            else:
                LoggerService.error(f"❌ MAX RETRIES REACHED: {flow_name} gave up.", flow_id=flow_id)

    @classmethod
    def upsert_job(cls, assistant: SyncAssistant):
        """
        Add or Update a job based on the Assistant Config.
        """
        if cls._scheduler is None:
            cls.start()
        
        # If scheduler is STILL None (running in another process), skip gracefully
        # If scheduler is STILL None (running in another process), skip gracefully
        if cls._scheduler is None:
            # raise Exception("Scheduler is not running (Locked). Please restart the server to fix the lock.")
            # FALLBACK: If we are in a worker process, we might need to write to DB directly?
            # For now, let's just log ERROR and raise to notify Frontend
            msg = f"CRITICAL: Scheduler is NOT running in this process. Job for '{assistant.name}' was NOT scheduled. Please RESTART the backend server."
            LoggerService.error(msg)
            raise Exception(msg)
            
        job_id = assistant.id
        
        # 1. Remove existing job and its slots (to update)
        all_jobs = cls._scheduler.get_jobs()
        for j in all_jobs:
            if j.id == job_id or j.id.startswith(f"{job_id}_slot_"):
                cls._scheduler.remove_job(j.id)
                LoggerService.info(f"Removed Persistent Job/Slot: {j.id}")
            
        # 2. Check if Schedule is Enabled
        if not assistant.schedule.enabled:
            LoggerService.info(f"Schedule Disabled for: {assistant.name}")
            return # Job removed and not re-added
            
        # 3. Determine Trigger
        trigger = None
        if assistant.schedule.cron_expression:
             # Convert Cron str to Trigger (Basic implementation)
             # "0 9 * * *" -> CronTrigger
             # We might need a parser or just pass args if clean
             try:
                trigger = CronTrigger.from_crontab(assistant.schedule.cron_expression)
             except:
                LoggerService.warn(f"Invalid Cron: {assistant.schedule.cron_expression}")
                return
        elif assistant.schedule.interval_minutes:
            trigger = IntervalTrigger(minutes=assistant.schedule.interval_minutes)
        elif assistant.schedule.fixed_times:
            # Multi-shot daily times: "HH:mm"
            # We add individual jobs for each time or use a cron-like string?
            # APScheduler CronTrigger supports list of hours/mins.
            try:
                hours = []
                minutes = []
                for t in assistant.schedule.fixed_times:
                    h, m = t.split(":")
                    if int(h) not in hours: hours.append(int(h))
                    if int(m) not in minutes: minutes.append(int(m))
                
                # Note: This trigger runs at ANY of these hours AND ANY of these minutes.
                # If they have 09:00 and 14:30, it would run at 09:00, 09:30, 14:00, 14:30.
                # Better approach: Add separate jobs for each time, but that complicates pruning.
                # OR: Use a custom trigger or just a more complex cron.
                # For now, let's use separate jobs with partitioned IDs or a simple check.
                
                # Robust approach: Loop and add separate jobs
                for i, t in enumerate(assistant.schedule.fixed_times):
                    try:
                        h, m = t.split(":")
                        new_job = cls._scheduler.add_job(
                            cls.execute_wrapper,
                            trigger=CronTrigger(hour=int(h), minute=int(m), second=0, timezone=assistant.schedule.timezone),
                            args=[assistant.dict(), 0],
                            id=f"{job_id}_slot_{i}",
                            name=f"{assistant.name} (at {t})",
                            replace_existing=True,
                            misfire_grace_time=3600,
                            coalesce=True,
                            jobstore='default'
                        )
                        next_run = getattr(new_job, 'next_run_time', 'Pending')
                        LoggerService.info(f"✅ Added Slot Job: {new_job.id}, Next run: {next_run}")
                    except Exception as slot_err:
                        import traceback
                        LoggerService.error(f"Failed to add slot job: {slot_err}\n{traceback.format_exc()}")
                
                LoggerService.info(f"✅ Finished Scheduling Multi-Slot Jobs for: {assistant.name}")
                return # We already added the jobs
            except Exception as e:
                import traceback
                LoggerService.error(f"Error in fixed_times loop: {e}\n{traceback.format_exc()}")
                return
        else:
            # Fallback or Manual Only
            LoggerService.warn(f"No valid schedule found for {assistant.name}")
            return

        # 4. Add Job
        # Target is execute_wrapper now
        cls._scheduler.add_job(
            cls.execute_wrapper,
            trigger=trigger,
            args=[assistant.dict(), 0], # retry_count=0
            id=job_id,
            name=assistant.name,
            replace_existing=True,
            misfire_grace_time=3600, # 1 Hour catch-up window
            coalesce=True, # Only run the latest missed job, don't stack them
            jobstore='default'
        )
        LoggerService.info(f"✅ Scheduled Job: {assistant.name} ({assistant.flow_type}) - Next run: {trigger.get_next_fire_time(None, datetime.now())}")

    @classmethod
    def remove_job(cls, job_id: str):
        if cls._scheduler and cls._scheduler.get_job(job_id):
            cls._scheduler.remove_job(job_id)
            LoggerService.info(f"Removed Job: {job_id}")

    @classmethod
    def list_jobs(cls):
        if not cls._scheduler:
            return []
        return [{"id": j.id, "name": j.name, "next_run": str(j.next_run_time)} for j in cls._scheduler.get_jobs()]

    @classmethod
    def trigger_job_now(cls, job_id: str):
        """
        Manually triggers a job to run immediately.
        """
        if not cls._scheduler:
            raise Exception("Scheduler not started")
            
        # Try to find existing job to get args
        job = cls._scheduler.get_job(job_id)
        if job:
             job_args = job.args # [config, retry_count]
             config = job_args[0]
             name = job.name
        else:
            # If Job doesn't exist (e.g. Schedule Disabled), we can't trigger it easily 
            # unless we lookup the Assistant from DB.
            # For now, assume UI calls this for ID that corresponds to a DB entry? 
            # Actually, `trigger_job_now` relies on `add_job` which needs the function.
            # If job is missing from scheduler, we can't clone it.
            # WORKAROUND: In a real app we fetch from DB. 
            # Here keeping it simple: Warning.
            raise Exception(f"Job {job_id} not active/scheduled. Enable schedule first.")
            
        # Add a one-off job
        cls._scheduler.add_job(
            cls.execute_wrapper,
            trigger='date',
            run_date=datetime.now(),
            args=[config, 0],
            id=f"{job_id}_manual_{datetime.now().timestamp()}",
            name=f"Manual: {name}",
            misfire_grace_time=3600
        )
        LoggerService.info(f"⚡ Manual Execution Triggered: {name}")

    @classmethod
    def pause_job(cls, job_id: str):
        if cls._scheduler and cls._scheduler.get_job(job_id):
            cls._scheduler.pause_job(job_id)
            LoggerService.info(f"⏸️ Paused Job: {job_id}")

    @classmethod
    def resume_job(cls, job_id: str):
        if cls._scheduler and cls._scheduler.get_job(job_id):
            cls._scheduler.resume_job(job_id)
            LoggerService.info(f"▶️ Resumed Job: {job_id}")

    @classmethod
    async def reset_stuck_jobs(cls):
        """
        Resets jobs stuck in 'PROCESSING' state for more than 1 hour.
        This handles server crashes where jobs were left in limbo.
        """
        from database import async_session
        from models import Job, JobStatus
        from sqlalchemy import select
        
        async with async_session() as session:
            # Heuristic: If scheduled more than 1 hour ago and still PROCESSING
            cutoff = datetime.utcnow() - timedelta(hours=1)
            result = await session.execute(
                select(Job).where(
                    Job.status == JobStatus.PROCESSING,
                    Job.scheduled_at < cutoff 
                )
            )
            stuck_jobs = result.scalars().all()
            
            if stuck_jobs:
                LoggerService.warn(f"🧟 Found {len(stuck_jobs)} Zombie Jobs (Stuck in PROCESSING > 1h). Resetting...")
                for job in stuck_jobs:
                    job.status = JobStatus.PENDING
                    job.attempts += 1
                    job.error = "Reset from Zombie state (Server Restart)"
                    job.scheduled_at = datetime.utcnow() + timedelta(minutes=1) # Retry in 1 min
                    session.add(job)
                
                await session.commit()
                LoggerService.info(f"✅ Resurrected {len(stuck_jobs)} Zombie Jobs.")
            else:
                LoggerService.info("✅ No Zombie Jobs found.")
