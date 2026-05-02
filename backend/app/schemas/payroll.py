from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class PayrollGenerateRequest(BaseModel):
    user_id: int
    month: int = Field(..., ge=1, le=12)
    year: int = Field(..., ge=2000)
    bonus: Optional[float] = Field(0.0, ge=0)
    overtime_pay: Optional[float] = Field(0.0, ge=0)
    other_deductions: Optional[float] = Field(0.0, ge=0)


class PayrollResponse(BaseModel):
    id: int
    user_id: int
    month: int
    year: int
    working_days: int
    total_hours: float
    extra_hours: float
    approved_leaves: int
    basic_salary: float
    bonus: float
    overtime_pay: float
    pf_contribution: float
    professional_tax: float
    other_deductions: float
    gross_salary: float
    net_salary: float
    generated_by: int
    generated_at: datetime

    class Config:
        from_attributes = True


class PayrollUpdateRequest(BaseModel):
    bonus: Optional[float] = Field(None, ge=0)
    overtime_pay: Optional[float] = Field(None, ge=0)
    other_deductions: Optional[float] = Field(None, ge=0)
