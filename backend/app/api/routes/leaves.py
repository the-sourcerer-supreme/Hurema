from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.leave import LeaveRequestCreate, LeaveRequestResponse, LeaveApprovalResponse
from app.utils.dependencies import get_current_user, get_db, require_roles
from app.services.leave_service import LeaveService

router = APIRouter(prefix="/leaves", tags=["leaves"])


@router.post("/request", response_model=LeaveRequestResponse)
async def request_leave(
    leave_request: LeaveRequestCreate,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await LeaveService.request_leave(session, current_user.id, leave_request)


@router.get("/me", response_model=list[LeaveRequestResponse])
async def get_my_leave_requests(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await LeaveService.list_leave_requests(session, current_user.id)


@router.post("/{request_id}/approve", response_model=LeaveApprovalResponse)
async def approve_leave_request(
    request_id: int,
    current_user=Depends(require_roles("Admin", "HR")),
    session: AsyncSession = Depends(get_db),
):
    return await LeaveService.approve_leave_request(session, request_id, current_user.id)
