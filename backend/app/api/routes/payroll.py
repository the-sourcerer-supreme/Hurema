from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.payroll import PayrollGenerateRequest, PayrollResponse
from app.utils.dependencies import get_current_user, get_db, require_roles
from app.services.payroll_service import PayrollService

router = APIRouter(prefix="/payroll", tags=["payroll"])


@router.post("/generate", response_model=PayrollResponse)
async def generate_payroll(
    payroll_request: PayrollGenerateRequest,
    current_user=Depends(require_roles("Admin", "Payroll")),
    session: AsyncSession = Depends(get_db),
):
    payroll = await PayrollService.generate_payroll(session, current_user.id, payroll_request)
    if not payroll:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unable to generate payroll")
    return payroll


@router.get("/me", response_model=list[PayrollResponse])
async def get_my_payrolls(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await PayrollService.list_payrolls_for_user(session, current_user.id)
