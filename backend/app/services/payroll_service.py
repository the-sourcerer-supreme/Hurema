from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.payroll import PayrollCRUD
from app.crud.user import UserCRUD
from app.schemas.payroll import PayrollGenerateRequest
from app.crud.attendance import AttendanceCRUD
from app.crud.leave import LeaveCRUD


class PayrollService:
    @staticmethod
    async def _calculate_payroll(session: AsyncSession, payroll_request: PayrollGenerateRequest) -> dict[str, float]:
        attendance_records = await AttendanceCRUD.list_attendance_for_user(session, payroll_request.user_id)
        approved_leaves = await LeaveCRUD.list_leave_requests_for_user(session, payroll_request.user_id)
        selected_leaves = [leave for leave in approved_leaves if leave.status == "Approved"]
        working_days = sum(1 for record in attendance_records if record.date.month == payroll_request.month and record.date.year == payroll_request.year)
        total_hours = sum((record.working_hours or 0.0) for record in attendance_records if record.date.month == payroll_request.month and record.date.year == payroll_request.year)
        extra_hours = sum((record.extra_hours or 0.0) for record in attendance_records if record.date.month == payroll_request.month and record.date.year == payroll_request.year)
        approved_leave_days = sum(leave.days_requested for leave in selected_leaves if leave.start_date.month == payroll_request.month and leave.start_date.year == payroll_request.year)
        user = await UserCRUD.get_user_by_id(session, payroll_request.user_id)
        basic_salary = float(user.profile.basic_salary) if user and user.profile else 0.0
        pf_contribution = basic_salary * 0.12
        professional_tax = 200.0
        gross_salary = basic_salary + (payroll_request.bonus or 0.0) + (payroll_request.overtime_pay or 0.0)
        net_salary = gross_salary - (pf_contribution + professional_tax + (payroll_request.other_deductions or 0.0))
        return {
            "working_days": working_days,
            "total_hours": total_hours,
            "extra_hours": extra_hours,
            "approved_leaves": approved_leave_days,
            "pf_contribution": pf_contribution,
            "professional_tax": professional_tax,
            "gross_salary": gross_salary,
            "net_salary": net_salary,
            "basic_salary": basic_salary,
        }

    @staticmethod
    async def generate_payroll(session: AsyncSession, generated_by: int, payroll_request: PayrollGenerateRequest):
        calculations = await PayrollService._calculate_payroll(session, payroll_request)
        if calculations["gross_salary"] <= 0:
            return None
        return await PayrollCRUD.create_payroll(
            session,
            payroll_request,
            generated_by,
            calculations,
            calculations["basic_salary"],
        )

    @staticmethod
    async def list_payrolls_for_user(session: AsyncSession, user_id: int):
        return await PayrollCRUD.list_payrolls_for_user(session, user_id)
