from __future__ import annotations
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.email_log import EmailLog


class EmailLogCRUD:
    @staticmethod
    async def create_log(
        db: AsyncSession,
        user_id: int,
        email: str,
        credential_sent: bool = False,
    ) -> EmailLog:
        log = EmailLog(
            user_id=user_id,
            email=email,
            credential_sent=credential_sent,
            sent_at=datetime.utcnow(),
        )
        db.add(log)
        await db.commit()
        await db.refresh(log)
        return log

    @staticmethod
    async def get_logs_by_user_id(db: AsyncSession, user_id: int) -> list[EmailLog]:
        result = await db.execute(select(EmailLog).where(EmailLog.user_id == user_id))
        return result.scalars().all()
