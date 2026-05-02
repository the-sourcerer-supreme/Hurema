from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.models.user import User
from app.models.payroll import Payroll
from app.models.leave import LeaveRequest
from app.models.attendance import Attendance


class DashboardService:
    @staticmethod
    async def get_summary(session: AsyncSession) -> dict:
        total_employees = await session.scalar(select(func.count(User.id)))
        active_employees = await session.scalar(select(func.count(User.id)).where(User.is_active == True))
        payrolls_processed = await session.scalar(select(func.count(Payroll.id)))
        leaves_last_month = await session.scalar(
            select(func.count(LeaveRequest.id)).where(LeaveRequest.status == "Approved")
        )
        absent_days_last_month = await session.scalar(
            select(func.count(Attendance.id)).where(Attendance.status == "Absent")
        )
        total_payout_last_month = await session.scalar(select(func.sum(Payroll.net_salary))) or 0.0
        return {
            "total_employees": total_employees or 0,
            "active_employees": active_employees or 0,
            "payrolls_processed": payrolls_processed or 0,
            "leaves_approved_last_month": leaves_last_month or 0,
            "absent_days_last_month": absent_days_last_month or 0,
            "total_payout_last_month": float(total_payout_last_month),
        }
