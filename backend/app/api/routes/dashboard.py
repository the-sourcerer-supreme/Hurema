from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.dashboard import DashboardSummary
from app.services.dashboard_service import DashboardService
from app.utils.dependencies import get_db, require_roles

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
async def get_dashboard_summary(
    current_user=Depends(require_roles("Admin", "HR", "Payroll")),
    session: AsyncSession = Depends(get_db),
):
    return await DashboardService.get_summary(session)
