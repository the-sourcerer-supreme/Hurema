from __future__ import annotations
from datetime import date
from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class EmployeeProfileBase(BaseModel):
    dob: Optional[date] = None
    address: Optional[str] = Field(None, max_length=400)
    nationality: Optional[str] = Field(None, max_length=100)
    gender: Optional[str] = Field(None, max_length=50)
    marital_status: Optional[str] = Field(None, max_length=50)
    mobile: Optional[str] = Field(None, max_length=20)
    personal_email: Optional[EmailStr] = None
    manager_id: Optional[int] = None
    location: Optional[str] = Field(None, max_length=150)
    bank_name: Optional[str] = Field(None, max_length=150)
    account_number: Optional[str] = Field(None, max_length=50)
    ifsc_code: Optional[str] = Field(None, max_length=20)
    pan_number: Optional[str] = Field(None, max_length=20)
    uan_number: Optional[str] = Field(None, max_length=50)
    basic_salary: Optional[float] = Field(None, ge=0)


class EmployeeProfileCreate(EmployeeProfileBase):
    user_id: int
    dob: Optional[date] = None
    address: Optional[str] = None
    nationality: Optional[str] = None
    gender: Optional[str] = None
    marital_status: Optional[str] = None
    mobile: Optional[str] = None
    personal_email: Optional[EmailStr] = None
    location: Optional[str] = None
    bank_name: Optional[str] = None
    account_number: Optional[str] = None
    ifsc_code: Optional[str] = None
    pan_number: Optional[str] = None
    uan_number: Optional[str] = None
    basic_salary: Optional[float] = None


class EmployeeProfileUpdate(EmployeeProfileBase):
    pass


class EmployeeProfileResponse(EmployeeProfileBase):
    id: int
    user_id: int

    class Config:
        from_attributes = True
