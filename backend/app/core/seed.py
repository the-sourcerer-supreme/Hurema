from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.attendance import Attendance
from app.models.audit_log import AuditLog
from app.models.company import CompanySetting
from app.models.leave import LeaveRequest
from app.models.leave_catalog import LeaveBalance, LeaveType
from app.models.payroll import Payroll
from app.models.payslip import Payslip
from app.models.profile import EmployeeProfile
from app.models.salary_structure import SalaryStructure
from app.models.user import User


DEMO_USERS = [
    {
        "employee_code": "EMP-001",
        "first_name": "Aarav",
        "last_name": "Admin",
        "email": "admin@empay.local",
        "password": "Admin@123",
        "role": "Admin",
        "department": "Operations",
        "designation": "Administrator",
        "location": "Bengaluru",
        "mobile": "9000000001",
    },
    {
        "employee_code": "EMP-002",
        "first_name": "Hina",
        "last_name": "HR",
        "email": "hr@empay.local",
        "password": "Hr@12345",
        "role": "HR Officer",
        "department": "People",
        "designation": "HR Officer",
        "location": "Bengaluru",
        "mobile": "9000000002",
    },
    {
        "employee_code": "EMP-003",
        "first_name": "Pranav",
        "last_name": "Payroll",
        "email": "payroll@empay.local",
        "password": "Payroll@123",
        "role": "Payroll Officer",
        "department": "Finance",
        "designation": "Payroll Officer",
        "location": "Bengaluru",
        "mobile": "9000000003",
    },
    {
        "employee_code": "EMP-004",
        "first_name": "Esha",
        "last_name": "Employee",
        "email": "employee@empay.local",
        "password": "Employee@123",
        "role": "Employee",
        "department": "Engineering",
        "designation": "Software Engineer",
        "location": "Bengaluru",
        "mobile": "9000000004",
    },
]

DEMO_LEAVE_TYPES = [
    ("Casual Leave", 12.0),
    ("Sick Leave", 6.0),
    ("Earned Leave", 15.0),
]


def _combine_dt(day: date, hour: int, minute: int = 0) -> datetime:
    return datetime.combine(day, time(hour=hour, minute=minute))


async def ensure_seed_data(session: AsyncSession) -> None:
    existing = await session.execute(select(User.id).limit(1))
    if existing.first() is not None:
        return

    today = date.today()
    current_month = date(today.year, today.month, 1)
    previous_month_last_day = current_month - timedelta(days=1)
    previous_month_first_day = date(previous_month_last_day.year, previous_month_last_day.month, 1)

    company = CompanySetting(company_name="EmPay Demo")
    session.add(company)

    leave_types: list[LeaveType] = []
    for name, default_balance in DEMO_LEAVE_TYPES:
        leave_type = LeaveType(name=name, default_balance=default_balance)
        session.add(leave_type)
        leave_types.append(leave_type)

    await session.flush()

    users: list[User] = []
    for index, demo_user in enumerate(DEMO_USERS):
        user = User(
            employee_code=demo_user["employee_code"],
            first_name=demo_user["first_name"],
            last_name=demo_user["last_name"],
            email=demo_user["email"],
            hashed_password=hash_password(demo_user["password"]),
            role=demo_user["role"],
            department=demo_user["department"],
            designation=demo_user["designation"],
            date_of_joining=today - timedelta(days=365 + (index * 30)),
            location=demo_user["location"],
            is_active=True,
            is_first_login=False,
            created_by=None if index == 0 else 1,
        )
        session.add(user)
        users.append(user)

    await session.flush()

    admin_user, hr_user, payroll_user, employee_user = users

    session.add_all(
        [
            EmployeeProfile(
                user_id=admin_user.id,
                mobile="9000000001",
                location="Bengaluru",
                basic_salary=95000,
                emergency_contact="9000000101",
                about="Keeps the workspace organized and helps unblock the team.",
                love_about_job="Helping every function run smoothly from one place.",
                hobbies="Reading, cycling",
                skills="Administration, operations, communication",
                certifications="SHRM Essentials",
                manager_name="",
            ),
            EmployeeProfile(
                user_id=hr_user.id,
                mobile="9000000002",
                location="Bengaluru",
                basic_salary=70000,
                emergency_contact="9000000102",
                about="Supports hiring, onboarding, and people programs.",
                love_about_job="Building a thoughtful employee experience.",
                hobbies="Music, travel",
                skills="Recruitment, employee relations, onboarding",
                certifications="HR Analytics",
                manager_name=f"{admin_user.first_name} {admin_user.last_name}",
                manager_id=admin_user.id,
            ),
            EmployeeProfile(
                user_id=payroll_user.id,
                mobile="9000000003",
                location="Bengaluru",
                basic_salary=76000,
                emergency_contact="9000000103",
                about="Maintains payroll cycles, deductions, and payroll records.",
                love_about_job="Making payroll feel boring in the best possible way.",
                hobbies="Cricket, films",
                skills="Payroll operations, compliance, spreadsheets",
                certifications="Payroll Management",
                manager_name=f"{admin_user.first_name} {admin_user.last_name}",
                manager_id=admin_user.id,
            ),
            EmployeeProfile(
                user_id=employee_user.id,
                mobile="9000000004",
                location="Bengaluru",
                basic_salary=68000,
                emergency_contact="9000000104",
                about="Builds product features and supports release work.",
                love_about_job="Turning messy ideas into useful software.",
                hobbies="Badminton, sketching",
                skills="React, Python, APIs",
                certifications="AWS Cloud Practitioner",
                manager_name=f"{hr_user.first_name} {hr_user.last_name}",
                manager_id=hr_user.id,
            ),
        ]
    )

    for user in users:
        for leave_type in leave_types:
            session.add(
                LeaveBalance(
                    user_id=user.id,
                    leave_type_id=leave_type.id,
                    balance=leave_type.default_balance,
                )
            )

    session.add_all(
        [
            SalaryStructure(user_id=admin_user.id, month_wage=95000, professional_tax=200, other_deduction=500),
            SalaryStructure(user_id=hr_user.id, month_wage=70000, professional_tax=200, other_deduction=250),
            SalaryStructure(user_id=payroll_user.id, month_wage=76000, professional_tax=200, other_deduction=300),
            SalaryStructure(user_id=employee_user.id, month_wage=68000, professional_tax=200, other_deduction=150),
        ]
    )

    sample_days: list[date] = []
    cursor = today
    while len(sample_days) < 5:
        if cursor.weekday() < 5:
            sample_days.append(cursor)
        cursor -= timedelta(days=1)

    for day in sample_days:
        for user in (hr_user, payroll_user, employee_user):
            check_in = _combine_dt(day, 9, 15 if user.id == employee_user.id and day == sample_days[0] else 0)
            check_out = _combine_dt(day, 18, 30 if user.id == payroll_user.id else 0)
            working_hours = round((check_out - check_in).total_seconds() / 3600, 2)
            session.add(
                Attendance(
                    user_id=user.id,
                    date=day,
                    check_in=check_in,
                    check_out=check_out,
                    working_hours=working_hours,
                    extra_hours=max(round(working_hours - 8, 2), 0),
                    status="Late" if check_in.time() > time(9, 5) else "Present",
                )
            )

    session.add(
        LeaveRequest(
            user_id=employee_user.id,
            leave_type="Casual Leave",
            start_date=today + timedelta(days=3),
            end_date=today + timedelta(days=4),
            days_requested=2,
            reason="Family event",
            status="Pending",
        )
    )
    session.add(
        LeaveRequest(
            user_id=hr_user.id,
            leave_type="Sick Leave",
            start_date=today - timedelta(days=10),
            end_date=today - timedelta(days=10),
            days_requested=1,
            reason="Medical appointment",
            status="Approved",
            approved_by=admin_user.id,
        )
    )

    payroll_month = previous_month_first_day.month
    payroll_year = previous_month_first_day.year
    days_in_month = monthrange(payroll_year, payroll_month)[1]
    for user, basic_salary, gross_salary, net_salary in (
        (hr_user, 35000, 71500, 66800),
        (payroll_user, 38000, 77750, 72530),
        (employee_user, 34000, 69200, 64670),
    ):
        payroll = Payroll(
            user_id=user.id,
            month=payroll_month,
            year=payroll_year,
            working_days=days_in_month - 8,
            total_hours=176.0,
            extra_hours=4.0,
            approved_leaves=1,
            basic_salary=basic_salary,
            bonus=2500.0,
            overtime_pay=1200.0,
            pf_contribution=round(basic_salary * 0.12, 2),
            professional_tax=200.0,
            other_deductions=150.0,
            gross_salary=gross_salary,
            net_salary=net_salary,
            generated_by=payroll_user.id,
        )
        session.add(payroll)
        await session.flush()
        session.add(Payslip(payroll_id=payroll.id, user_id=user.id))

    session.add_all(
        [
            AuditLog(actor_id=admin_user.id, action="Seeded demo workspace", target_type="system", target_id="seed"),
            AuditLog(actor_id=admin_user.id, action="Invited HR Officer", target_type="user", target_id=hr_user.employee_code),
            AuditLog(actor_id=admin_user.id, action="Invited Payroll Officer", target_type="user", target_id=payroll_user.employee_code),
            AuditLog(actor_id=admin_user.id, action="Invited Employee", target_type="user", target_id=employee_user.employee_code),
        ]
    )

    await session.commit()
