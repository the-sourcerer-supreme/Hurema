from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.attendance import AttendanceCRUD
from app.schemas.attendance import AttendanceCreate


class AttendanceService:
    @staticmethod
    async def check_in(session: AsyncSession, user_id: int, attendance_in: AttendanceCreate):
        existing = await AttendanceCRUD.get_attendance_by_user_and_date(session, user_id, attendance_in.date)
        if existing:
            return existing
        attendance = await AttendanceCRUD.create_attendance(session, user_id, attendance_in)
        attendance.check_in = datetime.utcnow()
        return await AttendanceCRUD.update_attendance(session, attendance)

    @staticmethod
    async def check_out(session: AsyncSession, user_id: int, date_value: datetime.date):
        attendance = await AttendanceCRUD.get_attendance_by_user_and_date(session, user_id, date_value)
        if not attendance:
            return None
        attendance.check_out = datetime.utcnow()
        if attendance.check_in:
            attendance.working_hours = (attendance.check_out - attendance.check_in).total_seconds() / 3600
        attendance.status = "Completed"
        return await AttendanceCRUD.update_attendance(session, attendance)

    @staticmethod
    async def list_for_user(session: AsyncSession, user_id: int):
        return await AttendanceCRUD.list_attendance_for_user(session, user_id)
