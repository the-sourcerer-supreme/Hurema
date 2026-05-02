from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.utils.dependencies import get_current_user, get_db, require_roles
from app.services.payslip_service import PayslipService
from app.crud.payroll import PayrollCRUD
from app.schemas.payslip import PayslipResponse, PayslipRequest

router = APIRouter(prefix="/payslips", tags=["payslips"])


@router.post("/generate", response_model=PayslipResponse)
async def generate_payslip(
    request: PayslipRequest,
    current_user=Depends(require_roles("Admin", "Payroll")),
    session: AsyncSession = Depends(get_db),
):
    payroll = await PayrollCRUD.get_payroll_by_id(session, request.payroll_id)
    if not payroll:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Payroll record not found")
    payslip = await PayslipService.create_payslip(session, request.payroll_id, payroll.user_id)
    return payslip


@router.get("/me", response_model=list[PayslipResponse])
async def get_my_payslips(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await PayslipService.list_payslips_for_user(session, current_user.id)
