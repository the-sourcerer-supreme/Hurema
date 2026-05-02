from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.attendance import AttendanceCreate, AttendanceResponse
from app.utils.dependencies import get_current_user, get_db
from app.services.attendance_service import AttendanceService

router = APIRouter(prefix="/attendance", tags=["attendance"])


@router.post("/check-in", response_model=AttendanceResponse)
async def check_in(
    attendance_in: AttendanceCreate,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await AttendanceService.check_in(session, current_user.id, attendance_in)


@router.post("/check-out", response_model=AttendanceResponse)
async def check_out(
    attendance_in: AttendanceCreate,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    attendance = await AttendanceService.check_out(session, current_user.id, attendance_in.date)
    if attendance is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance record not found")
    return attendance


@router.get("/me", response_model=list[AttendanceResponse])
async def get_my_attendance(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    return await AttendanceService.list_for_user(session, current_user.id)
