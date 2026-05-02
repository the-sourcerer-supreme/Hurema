from __future__ import annotations
from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    Boolean,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    employee_code = Column(String(32), unique=True, nullable=False, index=True)
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False)
    department = Column(String(100), nullable=False)
    designation = Column(String(100), nullable=False)
    date_of_joining = Column(Date, nullable=False)
    location = Column(String(150), nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    is_first_login = Column(Boolean, default=True, nullable=False)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    profile = relationship("EmployeeProfile", back_populates="user", uselist=False)
    attendance_records = relationship("Attendance", back_populates="user")
    leave_requests = relationship("LeaveRequest", back_populates="user")
    payrolls = relationship("Payroll", back_populates="user")
    payslips = relationship("Payslip", back_populates="user")
    email_logs = relationship("EmailLog", back_populates="user")
    creator = relationship("User", remote_side=[id])

    def __repr__(self) -> str:
        return f"<User(employee_code={self.employee_code}, email={self.email}, role={self.role})>"
