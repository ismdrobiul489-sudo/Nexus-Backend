from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from models import AppNotification
from datetime import datetime
from typing import List

class NotificationService:
    @staticmethod
    async def send_notification(session: AsyncSession, title: str, body: str, type: str = "info"):
        notification = AppNotification(
            title=title,
            body=body,
            type=type,
            created_at=datetime.utcnow()
        )
        session.add(notification)
        await session.commit()
        return notification

    @staticmethod
    async def send_success(session: AsyncSession, title: str, body: str):
        return await NotificationService.send_notification(session, f"✅ {title}", body, "success")

    @staticmethod
    async def send_error(session: AsyncSession, title: str, body: str):
        return await NotificationService.send_notification(session, f"❌ {title}", body, "error")

    @staticmethod
    async def get_latest(session: AsyncSession, limit: int = 10, unread_only: bool = True) -> List[AppNotification]:
        query = select(AppNotification).order_by(AppNotification.created_at.desc()).limit(limit)
        if unread_only:
            query = query.where(AppNotification.read == False)
        
        result = await session.execute(query)
        return result.scalars().all()

    @staticmethod
    async def mark_all_read(session: AsyncSession):
        notifications = await NotificationService.get_latest(session, limit=100, unread_only=True)
        for n in notifications:
            n.read = True
        session.add_all(notifications)
        await session.commit()
        return {"status": "success", "count": len(notifications)}

    @staticmethod
    async def clear_old(session: AsyncSession, days: int = 7):
        cutoff = datetime.utcnow() - timedelta(days=days)
        # Using SQLAlchemy delete
        # Note: Need timedelta imported
        from datetime import timedelta
        await session.execute(delete(AppNotification).where(AppNotification.created_at < cutoff))
        await session.commit()
