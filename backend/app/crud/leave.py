from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.leave import LeaveRequest
from app.schemas.leave import LeaveRequestCreate


class LeaveCRUD:
    @staticmethod
    async def create_leave_request(db: AsyncSession, user_id: int, leave_data: LeaveRequestCreate) -> LeaveRequest:
        leave_request = LeaveRequest(
            user_id=user_id,
            leave_type=leave_data.leave_type,
            start_date=leave_data.start_date,
            end_date=leave_data.end_date,
            days_requested=leave_data.days_requested,
            reason=leave_data.reason,
            status="Pending",
        )
        db.add(leave_request)
        await db.commit()
        await db.refresh(leave_request)
        return leave_request

    @staticmethod
    async def get_leave_request(db: AsyncSession, request_id: int) -> LeaveRequest | None:
        result = await db.execute(select(LeaveRequest).where(LeaveRequest.id == request_id))
        return result.scalars().first()

    @staticmethod
    async def list_leave_requests_for_user(db: AsyncSession, user_id: int) -> list[LeaveRequest]:
        result = await db.execute(select(LeaveRequest).where(LeaveRequest.user_id == user_id).order_by(LeaveRequest.created_at.desc()))
        return result.scalars().all()

    @staticmethod
    async def update_leave_request(db: AsyncSession, leave_request: LeaveRequest) -> LeaveRequest:
        db.add(leave_request)
        await db.commit()
        await db.refresh(leave_request)
        return leave_request
