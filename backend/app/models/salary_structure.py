from __future__ import annotations

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer
from sqlalchemy.sql import func

from app.core.database import Base


class SalaryStructure(Base):
    __tablename__ = "salary_structures"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    month_wage = Column(Float, nullable=False, default=50000.0)
    working_days_per_week = Column(Integer, nullable=False, default=5)
    break_hours = Column(Float, nullable=False, default=1.0)
    basic_percentage = Column(Float, nullable=False, default=50.0)
    hra_percentage = Column(Float, nullable=False, default=25.0)
    standard_allowance_percentage = Column(Float, nullable=False, default=8.33)
    performance_bonus_percentage = Column(Float, nullable=False, default=4.17)
    leave_travel_allowance_percentage = Column(Float, nullable=False, default=4.17)
    fixed_allowance_percentage = Column(Float, nullable=False, default=8.33)
    employee_pf_percentage = Column(Float, nullable=False, default=12.0)
    employer_pf_percentage = Column(Float, nullable=False, default=12.0)
    professional_tax = Column(Float, nullable=False, default=200.0)
    other_deduction = Column(Float, nullable=False, default=0.0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
