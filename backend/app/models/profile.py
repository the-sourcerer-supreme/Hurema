from __future__ import annotations
from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    Float,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class EmployeeProfile(Base):
    __tablename__ = "employee_profiles"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    dob = Column(Date, nullable=True)
    address = Column(String(400), nullable=True)
    nationality = Column(String(100), nullable=True)
    gender = Column(String(50), nullable=True)
    marital_status = Column(String(50), nullable=True)
    mobile = Column(String(20), nullable=True)
    personal_email = Column(String(255), nullable=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    location = Column(String(150), nullable=True)
    bank_name = Column(String(150), nullable=True)
    account_number = Column(String(50), nullable=True)
    ifsc_code = Column(String(20), nullable=True)
    pan_number = Column(String(20), nullable=True)
    uan_number = Column(String(50), nullable=True)
    basic_salary = Column(Float, nullable=False, default=0.0)
    emergency_contact = Column(String(100), nullable=True)
    about = Column(String(1000), nullable=True)
    love_about_job = Column(String(1000), nullable=True)
    hobbies = Column(String(1000), nullable=True)
    skills = Column(String(1000), nullable=True)
    certifications = Column(String(1000), nullable=True)
    profile_photo = Column(String, nullable=True)
    manager_name = Column(String(150), nullable=True)

    user = relationship("User", back_populates="profile", foreign_keys=[user_id])
    manager = relationship("User", foreign_keys=[manager_id])

    def __repr__(self) -> str:
        return f"<EmployeeProfile(user_id={self.user_id}, basic_salary={self.basic_salary})>"
