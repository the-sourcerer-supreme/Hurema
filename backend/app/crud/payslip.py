from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payslip import Payslip


class PayslipCRUD:
    @staticmethod
    async def create_payslip(db: AsyncSession, payroll_id: int, user_id: int, pdf_path: str | None = None) -> Payslip:
        payslip = Payslip(payroll_id=payroll_id, user_id=user_id, pdf_path=pdf_path)
        db.add(payslip)
        await db.commit()
        await db.refresh(payslip)
        return payslip

    @staticmethod
    async def get_payslips_for_user(db: AsyncSession, user_id: int) -> list[Payslip]:
        result = await db.execute(select(Payslip).where(Payslip.user_id == user_id).order_by(Payslip.generated_at.desc()))
        return result.scalars().all()
