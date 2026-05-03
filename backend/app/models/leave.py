from __future__ import annotations
from sqlalchemy import Column, Integer, ForeignKey, Date, DateTime, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class LeaveRequest(Base):
    __tablename__ = "leave_requests"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    leave_type = Column(String(100), nullable=False)
    start_date = Column(Date, nullable=False)
    end_date = Column(Date, nullable=False)
    days_requested = Column(Integer, nullable=False)
    reason = Column(String(500), nullable=True)
    status = Column(String(50), default="Pending", nullable=False)
    approved_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="leave_requests", foreign_keys=[user_id])

    def __repr__(self) -> str:
        return f"<LeaveRequest(user_id={self.user_id}, status={self.status})>"
