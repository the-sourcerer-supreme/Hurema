from fastapi import APIRouter, HTTPException, status, Depends
import logging
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.schemas.token import Token
from app.schemas.user import (
    UserCreate,
    UserLogin,
    ChangePasswordRequest,
    ForgotPasswordRequest,
    UserProfileResponse,
    UserResponse,
)
from app.services.auth_service import AuthService
from app.utils.dependencies import (
    get_current_user,
    get_db,
    get_optional_current_user,
    require_roles,
)
from app.crud.user import UserCRUD
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/create-user", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(
    user_create: UserCreate,
    session: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    try:
        total_users = await UserCRUD.count_users(session)
        if total_users == 0:
            if user_create.role != "Admin":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="The first user must be an Admin.",
                )
            creator_id = None
        else:
            if current_user is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Not authenticated",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            if current_user.role != "Admin":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Only Admin users can create new accounts.",
                )
            creator_id = current_user.id

        user, _temporary_password = await AuthService.create_employee(
            session=session,
            user_create=user_create,
            creator_id=creator_id,
        )
        return user
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Duplicate data detected. Please use unique email and employee details.",
        )
    except Exception as exc:
        logger.exception("Error creating employee")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to create employee account at this time.",
        )


@router.post("/login", response_model=Token)
async def login(user_login: UserLogin, session: AsyncSession = Depends(get_db)):
    user = await AuthService.authenticate_user(session, user_login.email, user_login.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return AuthService.create_token(user)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    session: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        await AuthService.change_password(
            session=session,
            user=current_user,
            current_password=payload.current_password,
            new_password=payload.new_password,
        )
        return {"message": "Password updated successfully."}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("/forgot-password")
async def forgot_password(
    payload: ForgotPasswordRequest,
    session: AsyncSession = Depends(get_db),
):
    success = await AuthService.forgot_password(session, payload.email)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Unable to process password reset request.",
        )
    return {
        "message": "If the email exists, a temporary password has been sent.",
        "status": "success",
    }


@router.get("/me", response_model=UserProfileResponse)
async def get_profile(current_user: User = Depends(get_current_user)):
    return current_user
