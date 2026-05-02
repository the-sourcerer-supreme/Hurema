from __future__ import annotations
from sqlalchemy import Column, Integer, ForeignKey, Float, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Payroll(Base):
    __tablename__ = "payroll"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    month = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    working_days = Column(Integer, nullable=False, default=0)
    total_hours = Column(Float, nullable=False, default=0.0)
    extra_hours = Column(Float, nullable=False, default=0.0)
    approved_leaves = Column(Integer, nullable=False, default=0)
    basic_salary = Column(Float, nullable=False, default=0.0)
    bonus = Column(Float, nullable=False, default=0.0)
    overtime_pay = Column(Float, nullable=False, default=0.0)
    pf_contribution = Column(Float, nullable=False, default=0.0)
    professional_tax = Column(Float, nullable=False, default=0.0)
    other_deductions = Column(Float, nullable=False, default=0.0)
    gross_salary = Column(Float, nullable=False, default=0.0)
    net_salary = Column(Float, nullable=False, default=0.0)
    generated_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="payrolls")

    def __repr__(self) -> str:
        return f"<Payroll(user_id={self.user_id}, month={self.month}, year={self.year})>"
