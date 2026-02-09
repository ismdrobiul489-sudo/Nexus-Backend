from fastapi import APIRouter
import psutil
import time
from datetime import datetime
from services.scheduler import SchedulerService

router = APIRouter(
    prefix="/api/health",
    tags=["System"]
)

start_time = time.time()

@router.get("/")
async def health_check():
    """
    Returns System Health, Uptime, and Active Scheduler Jobs.
    """
    process = psutil.Process()
    mem_info = process.memory_info()
    
    # Get Scheduler Info
    scheduler = SchedulerService.get_scheduler()
    all_jobs = []
    if scheduler:
        for store_alias in scheduler._jobstores:
            all_jobs.extend(scheduler.get_jobs(jobstore=store_alias))
    
    return {
        "status": "online",
        "server_time": datetime.now().isoformat(),
        "uptime_seconds": int(time.time() - start_time),
        "resource_usage": {
            "cpu_percent": process.cpu_percent(),
            "memory_mb": mem_info.rss / 1024 / 1024
        },
        "scheduler": {
            "running": getattr(scheduler, 'running', False),
            "jobs_count": len(all_jobs),
            "active_assistants": [j.id for j in all_jobs],
            "details": [{"id": j.id, "next_run": str(j.next_run_time), "store": getattr(j, 'jobstore', 'unknown')} for j in all_jobs]
        }
    }
