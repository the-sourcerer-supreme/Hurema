from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.profile import EmployeeProfileResponse, EmployeeProfileUpdate
from app.utils.dependencies import get_current_user, get_db
from app.crud.profile import EmployeeProfileCRUD

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=EmployeeProfileResponse)
async def get_my_profile(
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    profile = await EmployeeProfileCRUD.get_profile_by_user_id(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile


@router.put("/me", response_model=EmployeeProfileResponse)
async def update_my_profile(
    profile_update: EmployeeProfileUpdate,
    current_user=Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    profile = await EmployeeProfileCRUD.get_profile_by_user_id(session, current_user.id)
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return await EmployeeProfileCRUD.update_profile(session, profile, profile_update)
