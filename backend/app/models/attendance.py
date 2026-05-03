from __future__ import annotations
from sqlalchemy import Column, Integer, ForeignKey, Date, DateTime, Float, String
from sqlalchemy.orm import relationship
from app.core.database import Base


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    date = Column(Date, nullable=False)
    check_in = Column(DateTime(timezone=True), nullable=True)
    check_out = Column(DateTime(timezone=True), nullable=True)
    session_started_at = Column(DateTime(timezone=True), nullable=True)
    pause_started_at = Column(DateTime(timezone=True), nullable=True)
    paused_minutes = Column(Float, nullable=True, default=0.0)
    accumulated_hours = Column(Float, nullable=True, default=0.0)
    working_hours = Column(Float, nullable=True, default=0.0)
    extra_hours = Column(Float, nullable=True, default=0.0)
    status = Column(String(50), default="Pending", nullable=False)

    user = relationship("User", back_populates="attendance_records")

    def __repr__(self) -> str:
        return f"<Attendance(user_id={self.user_id}, date={self.date}, status={self.status})>"
