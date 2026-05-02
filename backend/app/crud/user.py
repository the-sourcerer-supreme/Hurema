from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import hash_password
from app.models.user import User
from typing import Optional
from app.schemas.user import UserCreate, UserUpdate


class UserCRUD:
    """CRUD operations for User entities."""

    @staticmethod
    async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
        result = await session.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    @staticmethod
    async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
        result = await session.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list_users(session: AsyncSession, skip: int = 0, limit: int = 25) -> list[User]:
        result = await session.execute(select(User).offset(skip).limit(limit))
        return result.scalars().all()

    @staticmethod
    async def count_users(session: AsyncSession) -> int:
        result = await session.execute(select(func.count()).select_from(User))
        return result.scalar_one()

    @staticmethod
    async def create_user(session: AsyncSession, user_data: UserCreate, employee_code: str, temporary_password: str, creator_id: Optional[int]) -> User:
        hashed_password = hash_password(temporary_password)
        user = User(
            employee_code=employee_code,
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            email=user_data.email,
            hashed_password=hashed_password,
            role=user_data.role,
            department=user_data.department,
            designation=user_data.designation,
            date_of_joining=user_data.date_of_joining,
            location=user_data.location,
            is_active=True,
            is_first_login=True,
            created_by=creator_id,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def update_user(session: AsyncSession, user_id: int, user_updates: UserUpdate) -> User | None:
        user = await UserCRUD.get_user_by_id(session, user_id)
        if not user:
            return None
        for field, value in user_updates.model_dump(exclude_unset=True).items():
            setattr(user, field, value)
        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def delete_user(session: AsyncSession, user_id: int) -> bool:
        user = await UserCRUD.get_user_by_id(session, user_id)
        if not user:
            return False
        await session.delete(user)
        await session.commit()
        return True

    @staticmethod
    async def set_password(session: AsyncSession, user: User, new_password: str, is_first_login: bool = False) -> User:
        user.hashed_password = hash_password(new_password)
        user.is_first_login = is_first_login
        await session.commit()
        await session.refresh(user)
        return user

    @staticmethod
    async def user_exists(session: AsyncSession, email: str) -> bool:
        return (await UserCRUD.get_user_by_email(session, email)) is not None
