from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel


class PayslipResponse(BaseModel):
    id: int
    payroll_id: int
    user_id: int
    pdf_path: Optional[str]
    generated_at: datetime

    class Config:
        from_attributes = True


class PayslipRequest(BaseModel):
    payroll_id: int
