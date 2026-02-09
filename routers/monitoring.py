from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from database import get_session
from models import Job, JobStatus
from sqlalchemy import select, func

router = APIRouter(prefix="/api/system", tags=["System"])

@router.get("/stats")
async def get_system_stats(session: AsyncSession = Depends(get_session)):
    """
    Returns system execution statistics from the Job table.
    """
    # Count Jobs by Status
    stmt = select(Job.status, func.count(Job.id)).group_by(Job.status)
    result = await session.execute(stmt)
    counts = dict(result.all())
    
    # Get Next Scheduled Job
    from datetime import datetime
    stmt_next = select(Job.scheduled_at).where(
        Job.status == JobStatus.PENDING,
        Job.scheduled_at > datetime.utcnow()
    ).order_by(Job.scheduled_at.asc()).limit(1)
    
    result_next = await session.execute(stmt_next)
    next_time = result_next.scalar_one_or_none()
    
    return {
        "status": "online",
        "jobs": {
            "total_success": counts.get(JobStatus.SUCCESS, 0),
            "total_failed": counts.get(JobStatus.FAILED, 0),
            "currently_processing": counts.get(JobStatus.PROCESSING, 0),
            "pending": counts.get(JobStatus.PENDING, 0),
            "delayed": counts.get(JobStatus.DELAYED, 0)
        },
        "next_scheduled_job": next_time.isoformat() if next_time else None
    }
