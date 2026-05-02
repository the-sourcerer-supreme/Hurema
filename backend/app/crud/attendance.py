from __future__ import annotations
from datetime import date, datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance import Attendance
from app.schemas.attendance import AttendanceCreate


class AttendanceCRUD:
    @staticmethod
    async def create_attendance(db: AsyncSession, user_id: int, attendance_in: AttendanceCreate) -> Attendance:
        attendance = Attendance(
            user_id=user_id,
            date=attendance_in.date,
            status="Present",
            check_in=datetime.utcnow(),
        )
        db.add(attendance)
        await db.commit()
        await db.refresh(attendance)
        return attendance

    @staticmethod
    async def get_attendance_by_user_and_date(db: AsyncSession, user_id: int, date_value: date) -> Attendance | None:
        result = await db.execute(
            select(Attendance).where(Attendance.user_id == user_id, Attendance.date == date_value)
        )
        return result.scalars().first()

    @staticmethod
    async def list_attendance_for_user(db: AsyncSession, user_id: int) -> list[Attendance]:
        result = await db.execute(select(Attendance).where(Attendance.user_id == user_id).order_by(Attendance.date.desc()))
        return result.scalars().all()

    @staticmethod
    async def update_attendance(db: AsyncSession, attendance: Attendance) -> Attendance:
        db.add(attendance)
        await db.commit()
        await db.refresh(attendance)
        return attendance
