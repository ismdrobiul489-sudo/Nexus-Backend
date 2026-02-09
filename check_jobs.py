
import asyncio
from datetime import datetime
from database import get_session
from models import Job, JobStatus
from sqlmodel import select

async def check_jobs():
    print(f"Current System Time (UTC): {datetime.utcnow()}")
    print(f"Current System Time (Local): {datetime.now()}")
    
    async for session in get_session():
        # Get pending jobs
        query = select(Job).where(Job.status == JobStatus.PENDING).order_by(Job.scheduled_at)
        result = await session.execute(query)
        jobs = result.scalars().all()
        
        print(f"\nFound {len(jobs)} PENDING jobs:")
        for job in jobs:
            diff = datetime.utcnow() - job.scheduled_at
            print(f" - Job {job.id} [{job.type}]")
            print(f"   Scheduled (UTC): {job.scheduled_at}")
            print(f"   Delay: {diff}")
            print(f"   Payload: {job.payload}")
            
        # Get recent logs or processing jobs
        query_proc = select(Job).where(Job.status == JobStatus.PROCESSING)
        result_proc = await session.execute(query_proc)
        processing = result_proc.scalars().all()
        print(f"\nFound {len(processing)} PROCESSING jobs (Stuck?):")
        for job in processing:
             print(f" - Job {job.id} [{job.type}] since {job.created_at}")

if __name__ == "__main__":
    asyncio.run(check_jobs())
