from __future__ import annotations
from datetime import date, datetime
from typing import Optional
from pydantic import BaseModel, Field


class LeaveRequestCreate(BaseModel):
    leave_type: str = Field(..., max_length=100)
    start_date: date
    end_date: date
    days_requested: int = Field(..., ge=1)
    reason: Optional[str] = Field(None, max_length=500)


class LeaveRequestResponse(BaseModel):
    id: int
    user_id: int
    leave_type: str
    start_date: date
    end_date: date
    days_requested: int
    reason: Optional[str]
    status: str
    approved_by: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class LeaveApprovalResponse(BaseModel):
    message: str
    request_id: int
    status: str
