from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import db_manager
from app.core.security import decode_token
from app.crud.user import UserCRUD
from app.models.user import User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="/auth/login", auto_error=False)


async def get_db() -> AsyncSession:
    async for session in db_manager.get_session():
        yield session


async def get_current_user(
    token: str = Depends(oauth2_scheme),
    session: AsyncSession = Depends(get_db),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = decode_token(token)
    if payload is None:
        raise credentials_exception

    user_id = payload.get("user_id")
    if user_id is None:
        raise credentials_exception

    user = await UserCRUD.get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return user


async def get_optional_current_user(
    token: str | None = Depends(oauth2_scheme_optional),
    session: AsyncSession = Depends(get_db),
) -> User | None:
    if not token:
        return None

    payload = decode_token(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("user_id")
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = await UserCRUD.get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


def require_roles(*allowed_roles: str):
    async def role_dependency(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Operation not permitted for this role.",
            )
        return current_user

    return role_dependency
