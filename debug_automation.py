
import asyncio
from services.scheduler import SchedulerService
from services.logger_service import LoggerService
from database import async_session
from sqlmodel import select
from models import FlowConfig, Job

async def debug_status():
    print("\n--- 📅 APScheduler Active Jobs ---")
    jobs = SchedulerService.list_jobs()
    if not jobs:
        print("No active jobs in scheduler.")
    for j in jobs:
        print(f"ID: {j['id']} | Name: {j['name']} | Next Run: {j['next_run']}")

    print("\n--- 📝 Recent Database Logs ---")
    logs = LoggerService.get_logs(limit=20)
    for l in logs:
        timestamp = l.get('timestamp', 'N/A')
        level = l.get('level', 'INFO')
        msg = l.get('message', '')
        print(f"[{timestamp}] {level}: {msg}")

    print("\n--- 🤖 Flow Configs in DB ---")
    async with async_session() as session:
        flows = (await session.execute(select(FlowConfig))).scalars().all()
        for f in flows:
            print(f"ID: {f.id} | Name: {f.name} | Active: {f.is_active} | Type: {f.source_type}")

if __name__ == "__main__":
    asyncio.run(debug_status())
