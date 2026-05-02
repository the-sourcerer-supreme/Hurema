from fastapi import APIRouter, Depends, HTTPException, status
from app.schemas.user import UserResponse
from app.utils.dependencies import get_db, require_roles
from app.crud.user import UserCRUD
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/", response_model=list[UserResponse])
async def list_users(
    session: AsyncSession = Depends(get_db),
    current_user=Depends(require_roles("Admin", "HR")),
):
    users = await UserCRUD.list_users(session)
    return users


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(user_id: int, session: AsyncSession = Depends(get_db), current_user=Depends(require_roles("Admin", "HR", "Payroll", "Employee"))):
    user = await UserCRUD.get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    return user
