from __future__ import annotations
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payroll import Payroll
from app.schemas.payroll import PayrollGenerateRequest


class PayrollCRUD:
    @staticmethod
    async def create_payroll(db: AsyncSession, payroll_data: PayrollGenerateRequest, generated_by: int, calculations: dict[str, float], basic_salary: float) -> Payroll:
        payroll = Payroll(
            user_id=payroll_data.user_id,
            month=payroll_data.month,
            year=payroll_data.year,
            working_days=calculations["working_days"],
            total_hours=calculations["total_hours"],
            extra_hours=calculations["extra_hours"],
            approved_leaves=calculations["approved_leaves"],
            basic_salary=basic_salary,
            bonus=payroll_data.bonus or 0.0,
            overtime_pay=payroll_data.overtime_pay or 0.0,
            pf_contribution=calculations["pf_contribution"],
            professional_tax=calculations["professional_tax"],
            other_deductions=payroll_data.other_deductions or 0.0,
            gross_salary=calculations["gross_salary"],
            net_salary=calculations["net_salary"],
            generated_by=generated_by,
        )
        db.add(payroll)
        await db.commit()
        await db.refresh(payroll)
        return payroll

    @staticmethod
    async def get_payroll_by_id(db: AsyncSession, payroll_id: int) -> Payroll | None:
        result = await db.execute(select(Payroll).where(Payroll.id == payroll_id))
        return result.scalars().first()

    @staticmethod
    async def list_payrolls_for_user(db: AsyncSession, user_id: int) -> list[Payroll]:
        result = await db.execute(select(Payroll).where(Payroll.user_id == user_id).order_by(Payroll.generated_at.desc()))
        return result.scalars().all()
