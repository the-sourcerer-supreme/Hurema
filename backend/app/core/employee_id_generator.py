from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.user import User


def _normalize_segment(value: str) -> str:
    normalized = "".join([ch for ch in value.strip().upper() if ch.isalpha()])
    return (normalized + "XX")[:2]


async def generate_employee_code(
    session: AsyncSession,
    first_name: str,
    last_name: str,
    date_of_joining_year: int,
) -> str:
    prefix = "OI"
    first_segment = _normalize_segment(first_name)
    last_segment = _normalize_segment(last_name)
    year = str(date_of_joining_year)
    pattern = f"{prefix}____{year}%"

    result = await session.execute(
        select(func.count()).select_from(User).where(User.employee_code.like(pattern))
    )
    count = result.scalar_one() or 0
    serial = count + 1
    return f"{prefix}{first_segment}{last_segment}{year}{serial:04d}"
