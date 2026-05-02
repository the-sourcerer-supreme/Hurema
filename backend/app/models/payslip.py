from __future__ import annotations
from sqlalchemy import Column, Integer, ForeignKey, String, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class Payslip(Base):
    __tablename__ = "payslips"

    id = Column(Integer, primary_key=True, index=True)
    payroll_id = Column(Integer, ForeignKey("payroll.id"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pdf_path = Column(String(500), nullable=True)
    generated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="payslips")
    payroll = relationship("Payroll")

    def __repr__(self) -> str:
        return f"<Payslip(user_id={self.user_id}, payroll_id={self.payroll_id})>"
