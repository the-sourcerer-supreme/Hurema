from __future__ import annotations
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.profile import EmployeeProfile
from app.schemas.profile import EmployeeProfileCreate, EmployeeProfileUpdate


class EmployeeProfileCRUD:
    @staticmethod
    async def get_profile_by_user_id(db: AsyncSession, user_id: int) -> Optional[EmployeeProfile]:
        result = await db.execute(select(EmployeeProfile).where(EmployeeProfile.user_id == user_id))
        return result.scalars().first()

    @staticmethod
    async def create_profile(db: AsyncSession, profile_in: EmployeeProfileCreate) -> EmployeeProfile:
        profile = EmployeeProfile(**profile_in.model_dump())
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def update_profile(db: AsyncSession, profile: EmployeeProfile, profile_in: EmployeeProfileUpdate) -> EmployeeProfile:
        for field, value in profile_in.model_dump(exclude_unset=True).items():
            setattr(profile, field, value)
        db.add(profile)
        await db.commit()
        await db.refresh(profile)
        return profile

    @staticmethod
    async def delete_profile(db: AsyncSession, profile: EmployeeProfile) -> None:
        await db.delete(profile)
        await db.commit()
