from __future__ import annotations
from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_employees: int
    active_employees: int
    payrolls_processed: int
    leaves_approved_last_month: int
    absent_days_last_month: int
    total_payout_last_month: float
