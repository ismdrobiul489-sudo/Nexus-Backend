from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, desc, func
from models import IdeaHistory
from datetime import datetime
from typing import List

class MemoryService:
    @staticmethod
    async def get_history(session: AsyncSession, limit: int = 500) -> List[IdeaHistory]:
        """Fetches all history items, sorted by newest first."""
        statement = select(IdeaHistory).order_by(desc(IdeaHistory.timestamp)).limit(limit)
        results = await session.execute(statement)
        return results.scalars().all()

    @staticmethod
    async def get_recent_ideas(flow_id: str, session: AsyncSession, limit: int = 50) -> List[str]:
        """Fetches recent concepts for a specific flow, mirroring memoryService.ts logic."""
        statement = (
            select(IdeaHistory.concept)
            .where(IdeaHistory.flow_id == flow_id)
            .order_by(desc(IdeaHistory.timestamp))
            .limit(limit)
        )
        results = await session.execute(statement)
        return results.scalars().all()

    @staticmethod
    async def save_idea(flow_id: str, concept: str, session: AsyncSession):
        """Saves a new concept and enforces the 500-item global limit."""
        new_item = IdeaHistory(
            flow_id=flow_id,
            concept=concept,
            timestamp=datetime.utcnow()
        )
        session.add(new_item)
        await session.commit()

        # Enforce global limit of 500 entries (1:1 parity with logger.ts/memoryService.ts behavior)
        total_count_statement = select(func.count(IdeaHistory.id))
        total_count = (await session.execute(total_count_statement)).scalar()

        if total_count > 500:
            # Find and delete oldest entries
            oldest_statement = (
                select(IdeaHistory)
                .order_by(IdeaHistory.timestamp)
                .limit(total_count - 500)
            )
            oldest_items = (await session.execute(oldest_statement)).scalars().all()
            for item in oldest_items:
                await session.delete(item)
            await session.commit()
            
        return new_item
