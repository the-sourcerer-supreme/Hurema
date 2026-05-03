from __future__ import annotations

from sqlalchemy import Column, Float, ForeignKey, Integer, String

from app.core.database import Base


class LeaveType(Base):
    __tablename__ = "leave_types"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    default_balance = Column(Float, nullable=False, default=0.0)


class LeaveBalance(Base):
    __tablename__ = "leave_balances"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    leave_type_id = Column(Integer, ForeignKey("leave_types.id"), nullable=False)
    balance = Column(Float, nullable=False, default=0.0)
