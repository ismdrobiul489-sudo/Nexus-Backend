import asyncio
from database import init_db, async_session
from models import Job
from sqlalchemy import select

async def main():
    await init_db()
    async with async_session() as session:
        job_id = "589ac969-772f-46c0-b830-4eda782f84a3"
        job = await session.get(Job, job_id)
        if job:
            print(f"FAILED JOB DETAILS:")
            print(f"ID: {job.id}")
            print(f"Type: {job.type}")
            print(f"Status: {job.status}")
            print(f"Error: {job.error}")
            print(f"Payload: {job.payload}")
        else:
            print("Job not found.")

if __name__ == "__main__":
    asyncio.run(main())
