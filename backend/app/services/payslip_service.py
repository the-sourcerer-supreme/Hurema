from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.payslip import PayslipCRUD


class PayslipService:
    @staticmethod
    async def create_payslip(session: AsyncSession, payroll_id: int, user_id: int, pdf_path: str | None = None):
        return await PayslipCRUD.create_payslip(session, payroll_id, user_id, pdf_path)

    @staticmethod
    async def list_payslips_for_user(session: AsyncSession, user_id: int):
        return await PayslipCRUD.get_payslips_for_user(session, user_id)
