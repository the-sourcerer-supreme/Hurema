from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel


class AttendanceCreate(BaseModel):
    date: date


class AttendanceResponse(BaseModel):
    id: int
    user_id: int
    date: date
    check_in: Optional[datetime]
    check_out: Optional[datetime]
    working_hours: Optional[float]
    extra_hours: Optional[float]
    status: str

    class Config:
        from_attributes = True


class AttendanceSummary(BaseModel):
    present_days: int
    total_hours: float
    extra_hours: float
