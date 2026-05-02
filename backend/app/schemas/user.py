from __future__ import annotations
from datetime import date, datetime
from typing import Literal, Optional
from pydantic import BaseModel, EmailStr, Field


UserRole = Literal["Admin", "HR", "Employee", "Payroll Officer"]


class UserBase(BaseModel):
    first_name: str = Field(..., min_length=2, max_length=100)
    last_name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    department: str = Field(..., min_length=2, max_length=100)
    designation: str = Field(..., min_length=2, max_length=100)
    date_of_joining: date
    location: str = Field(..., min_length=2, max_length=150)
    role: UserRole


class UserCreate(UserBase):
    date_of_birth: Optional[date] = None
    address: Optional[str] = Field(None, min_length=5, max_length=400)
    nationality: Optional[str] = Field(None, min_length=2, max_length=100)
    gender: Optional[str] = Field(None, min_length=2, max_length=50)
    marital_status: Optional[str] = Field(None, min_length=2, max_length=50)
    mobile: Optional[str] = Field(None, min_length=8, max_length=20)
    personal_email: Optional[EmailStr] = None
    manager_id: Optional[int] = None
    bank_name: Optional[str] = Field(None, min_length=2, max_length=150)
    account_number: Optional[str] = Field(None, min_length=6, max_length=50)
    ifsc_code: Optional[str] = Field(None, min_length=7, max_length=20)
    pan_number: Optional[str] = Field(None, min_length=10, max_length=20)
    uan_number: Optional[str] = Field(None, min_length=6, max_length=50)
    basic_salary: Optional[float] = Field(None, gt=0)


class UserLogin(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=8)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=8)
    new_password: str = Field(..., min_length=8)


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class UserResponse(BaseModel):
    id: int
    employee_code: str
    first_name: str
    last_name: str
    email: EmailStr
    role: str
    department: str
    designation: str
    date_of_joining: date
    location: str
    is_active: bool
    is_first_login: bool
    created_by: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class UserProfileResponse(UserResponse):
    pass


class UserUpdate(BaseModel):
    first_name: Optional[str]
    last_name: Optional[str]
    department: Optional[str]
    designation: Optional[str]
    location: Optional[str]
    role: Optional[str]
    is_active: Optional[bool]

    class Config:
        from_attributes = True
