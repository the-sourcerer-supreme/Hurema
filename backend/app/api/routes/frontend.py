from __future__ import annotations

from calendar import month_name, monthrange
from collections import defaultdict
from datetime import date, datetime, time, timedelta
import secrets
import threading
import time as time_module
from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import delete, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.core.employee_id_generator import generate_employee_code
from app.core.email_service import EmailService
from app.core.security import create_access_token, decode_token, hash_password, verify_password
from app.models.attendance import Attendance
from app.models.audit_log import AuditLog
from app.models.company import CompanySetting
from app.models.email_log import EmailLog
from app.models.leave import LeaveRequest
from app.models.leave_catalog import LeaveBalance, LeaveType
from app.models.payroll import Payroll
from app.models.payslip import Payslip
from app.models.profile import EmployeeProfile
from app.models.salary_structure import SalaryStructure
from app.models.user import User
from app.utils.dependencies import get_db

router = APIRouter(prefix="/api", tags=["frontend"])

SESSION_COOKIE = "empay_session"
ALLOWED_ROLES = {"Admin", "Employee", "HR Officer", "Payroll Officer"}
PAYROLL_ROLES = {"Admin", "Payroll Officer"}
REVIEW_LEAVE_ROLES = {"Admin", "HR Officer"}
DIRECTORY_ROLES = {"Admin", "HR Officer", "Payroll Officer"}
AUTH_RATE_LIMIT_WINDOW = 10 * 60
AUTH_RATE_LIMIT_MAX_ATTEMPTS = 10

_auth_attempts: dict[str, list[float]] = {}
_auth_lock = threading.Lock()


def _full_name(user: User) -> str:
    return f"{user.first_name} {user.last_name}".strip()


def _client_key(request: Request, scope: str) -> str:
    client_host = request.client.host if request.client else "unknown"
    return f"{scope}:{client_host}"


def _register_attempt(request: Request, scope: str) -> None:
    now = time_module.time()
    key = _client_key(request, scope)
    with _auth_lock:
        attempts = [timestamp for timestamp in _auth_attempts.get(key, []) if now - timestamp < AUTH_RATE_LIMIT_WINDOW]
        attempts.append(now)
        _auth_attempts[key] = attempts


def _clear_attempts(request: Request, scope: str) -> None:
    key = _client_key(request, scope)
    with _auth_lock:
        _auth_attempts.pop(key, None)


def _enforce_auth_rate_limit(request: Request, scope: str) -> None:
    now = time_module.time()
    key = _client_key(request, scope)
    with _auth_lock:
        attempts = [timestamp for timestamp in _auth_attempts.get(key, []) if now - timestamp < AUTH_RATE_LIMIT_WINDOW]
        _auth_attempts[key] = attempts
    if len(attempts) >= AUTH_RATE_LIMIT_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many attempts. Please wait a few minutes and try again.")


def _is_secure_request(request: Request) -> bool:
    forwarded_proto = request.headers.get("x-forwarded-proto", "")
    if forwarded_proto:
        return forwarded_proto.split(",", 1)[0].strip().lower() == "https"
    return request.url.scheme == "https"


def _set_auth_cookies(request: Request, response: Response, token: str) -> None:
    secure = _is_secure_request(request)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=secure,
        max_age=60 * 60 * 24 * 7,
        path="/",
    )


def _clear_auth_cookies(request: Request, response: Response) -> None:
    secure = _is_secure_request(request)
    response.delete_cookie(SESSION_COOKIE, path="/", secure=secure, samesite="lax")


def _require_csrf(request: Request, csrf_header: str | None) -> None:
    origin = request.headers.get("origin")
    referer = request.headers.get("referer")
    host = request.headers.get("host", "")
    if origin and urlparse(origin).netloc != host:
        raise HTTPException(status_code=403, detail="Cross-origin requests are not allowed.")
    if referer and urlparse(referer).netloc and urlparse(referer).netloc != host:
        raise HTTPException(status_code=403, detail="Cross-origin requests are not allowed.")
    token = request.cookies.get(SESSION_COOKIE)
    payload = decode_token(token) if token else None
    expected = str(payload.get("csrf", "")) if payload else ""
    if not expected or not csrf_header or not secrets.compare_digest(expected, csrf_header):
        raise HTTPException(status_code=403, detail="Your session could not be verified. Refresh and try again.")


def _validate_password(password: str) -> None:
    password = str(password or "")
    if len(password) < 12:
        raise HTTPException(status_code=400, detail="Password must be at least 12 characters long.")
    checks = [
        any(character.islower() for character in password),
        any(character.isupper() for character in password),
        any(character.isdigit() for character in password),
        any(not character.isalnum() for character in password),
    ]
    if not all(checks):
        raise HTTPException(
            status_code=400,
            detail="Password must include uppercase, lowercase, number, and special character.",
        )


def _validate_role(role: str) -> str:
    normalized_role = str(role or "").strip()
    if normalized_role not in ALLOWED_ROLES:
        raise HTTPException(status_code=400, detail="Please select a valid role.")
    return normalized_role


def _validate_profile_photo(value: str) -> str:
    profile_photo = str(value or "").strip()
    if not profile_photo:
        return ""
    if not profile_photo.startswith("data:image/"):
        raise HTTPException(status_code=400, detail="Profile photo must be an image.")
    if len(profile_photo) > 2_800_000:
        raise HTTPException(status_code=400, detail="Profile photo is too large. Please upload a smaller image.")
    return profile_photo


def _validate_company_logo(value: str) -> str:
    return _validate_profile_photo(value)


def _month_bounds(month_value: str | None) -> tuple[date, date]:
    if month_value:
        year, month = [int(part) for part in month_value.split("-", 1)]
    else:
        today = date.today()
        year, month = today.year, today.month
    start = date(year, month, 1)
    end = date(year, month, monthrange(year, month)[1])
    return start, end


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _split_name(full_name: str) -> tuple[str, str]:
    parts = [part for part in str(full_name or "").strip().split() if part]
    if not parts:
        return "New", "User"
    if len(parts) == 1:
        return parts[0], "User"
    return parts[0], " ".join(parts[1:])


def _role_permissions(role: str) -> dict[str, bool]:
    return {
        "canViewAttendanceDirectory": role in DIRECTORY_ROLES,
        "canReviewLeaves": role in REVIEW_LEAVE_ROLES,
        "canAccessPayroll": role in PAYROLL_ROLES or role == "Employee",
    }


def _business_days(start: date, end: date) -> int:
    total = 0
    cursor = start
    while cursor <= end:
        if cursor.weekday() < 5:
            total += 1
        cursor = cursor.fromordinal(cursor.toordinal() + 1)
    return total


def _parse_datetime(day_value: str, time_value: str) -> datetime:
    local_tz = datetime.now().astimezone().tzinfo
    return datetime.combine(date.fromisoformat(day_value), time.fromisoformat(time_value), tzinfo=local_tz)


def _serialize_datetime(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _worked_hours(record: Attendance, current_time: datetime | None = None) -> float:
    if not record.check_in and not record.session_started_at:
        return 0.0
    if record.session_started_at:
        end_time = current_time or datetime.now().astimezone()
        paused_minutes = float(record.paused_minutes or 0)
        if record.pause_started_at:
            pause_end = current_time or record.pause_started_at
            paused_minutes += max((pause_end - record.pause_started_at).total_seconds() / 60, 0)
        seconds = max((end_time - record.session_started_at).total_seconds() - paused_minutes * 60, 0)
        return round(float(record.accumulated_hours or 0) + seconds / 3600, 2)
    if record.working_hours:
        return round(record.working_hours or 0, 2)
    end_time = record.check_out or current_time
    if not end_time or not record.check_in:
        return round(record.accumulated_hours or 0, 2)
    paused_minutes = float(record.paused_minutes or 0)
    if record.pause_started_at and not record.check_out:
        pause_end = current_time or record.pause_started_at
        paused_minutes += max((pause_end - record.pause_started_at).total_seconds() / 60, 0)
    seconds = max((end_time - record.check_in).total_seconds() - paused_minutes * 60, 0)
    return round(float(record.accumulated_hours or 0) + seconds / 3600, 2)


def _currency_text(amount: float) -> str:
    return f"INR {round(float(amount or 0), 2):,.2f}"


def _month_label(month_value: str) -> str:
    year, month_number = [int(part) for part in month_value.split("-", 1)]
    return f"{month_name[month_number]} {year}"


def _month_parts(month_value: str | None) -> tuple[int, int]:
    if month_value:
        year, month_number = [int(part) for part in month_value.split("-", 1)]
        return year, month_number
    today = date.today()
    return today.year, today.month


def _month_key(year: int, month_number: int) -> str:
    return f"{year}-{month_number:02d}"


def _shift_month(year: int, month_number: int, delta: int) -> tuple[int, int]:
    total = year * 12 + (month_number - 1) + delta
    shifted_year = total // 12
    shifted_month = total % 12 + 1
    return shifted_year, shifted_month


def _month_window(month_value: str | None, count: int = 5) -> list[dict[str, Any]]:
    year, month_number = _month_parts(month_value)
    items: list[dict[str, Any]] = []
    for delta in range(count - 1, -1, -1):
        item_year, item_month = _shift_month(year, month_number, -delta)
        item_start = date(item_year, item_month, 1)
        item_end = date(item_year, item_month, monthrange(item_year, item_month)[1])
        items.append(
            {
                "year": item_year,
                "month": item_month,
                "key": _month_key(item_year, item_month),
                "label": month_name[item_month][:3],
                "start": item_start,
                "end": item_end,
            }
        )
    return items


def _compact_currency_text(amount: float) -> str:
    value = float(amount or 0)
    absolute = abs(value)
    if absolute >= 100000:
        text = f"₹{value / 100000:.1f}L"
        return text.replace(".0L", "L")
    if absolute >= 1000:
        text = f"₹{value / 1000:.1f}K"
        return text.replace(".0K", "K")
    return f"₹{round(value):,}"


def _percent_text(value: float) -> str:
    return f"{round(float(value or 0), 1)}%"


def _safe_ratio(numerator: float, denominator: float) -> float:
    if denominator <= 0:
        return 0.0
    return float(numerator or 0) / float(denominator)


def _overlap_days(start_a: date, end_a: date, start_b: date, end_b: date) -> int:
    if end_a < start_b or end_b < start_a:
        return 0
    overlap_start = max(start_a, start_b)
    overlap_end = min(end_a, end_b)
    return max((overlap_end - overlap_start).days + 1, 0)


def _amount_in_words(amount: float) -> str:
    ones = [
        "Zero",
        "One",
        "Two",
        "Three",
        "Four",
        "Five",
        "Six",
        "Seven",
        "Eight",
        "Nine",
        "Ten",
        "Eleven",
        "Twelve",
        "Thirteen",
        "Fourteen",
        "Fifteen",
        "Sixteen",
        "Seventeen",
        "Eighteen",
        "Nineteen",
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]

    def two_digits(value: int) -> str:
        if value < 20:
            return ones[value]
        prefix = tens[value // 10]
        suffix = value % 10
        return prefix if suffix == 0 else f"{prefix}-{ones[suffix]}"

    def three_digits(value: int) -> str:
        if value < 100:
            return two_digits(value)
        remainder = value % 100
        base = f"{ones[value // 100]} Hundred"
        return base if remainder == 0 else f"{base} {two_digits(remainder)}"

    number = int(round(float(amount or 0)))
    if number == 0:
        return "Zero Rupees Only"

    parts: list[str] = []
    crores, number = divmod(number, 10_000_000)
    lakhs, number = divmod(number, 100_000)
    thousands, number = divmod(number, 1_000)
    if crores:
        parts.append(f"{two_digits(crores)} Crore")
    if lakhs:
        parts.append(f"{two_digits(lakhs)} Lakh")
    if thousands:
        parts.append(f"{two_digits(thousands)} Thousand")
    if number:
        parts.append(three_digits(number))
    return " ".join(parts) + " Rupees Only"


def _pdf_escape(value: str) -> str:
    return str(value or "").replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)").replace("\r", " ").replace("\n", " ")


def _pdf_text(
    text: str,
    x: float,
    y: float,
    *,
    size: float = 12,
    font: str = "F1",
    color: tuple[float, float, float] = (0, 0, 0),
) -> str:
    red, green, blue = color
    return (
        f"BT /{font} {size:.2f} Tf "
        f"{red:.3f} {green:.3f} {blue:.3f} rg "
        f"1 0 0 1 {x:.2f} {y:.2f} Tm "
        f"({_pdf_escape(text)}) Tj ET"
    )


def _pdf_text_right(
    text: str,
    x_right: float,
    y: float,
    *,
    size: float = 12,
    font: str = "F1",
    color: tuple[float, float, float] = (0, 0, 0),
) -> str:
    estimated_width = len(str(text or "")) * size * (0.56 if font == "F1" else 0.60)
    return _pdf_text(text, x_right - estimated_width, y, size=size, font=font, color=color)


def _pdf_line(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    width: float = 1,
    color: tuple[float, float, float] = (0.72, 0.72, 0.72),
) -> str:
    red, green, blue = color
    return f"q {width:.2f} w {red:.3f} {green:.3f} {blue:.3f} RG {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S Q"


def _pdf_rect(
    x: float,
    y: float,
    width: float,
    height: float,
    *,
    fill: tuple[float, float, float] | None = None,
    stroke: tuple[float, float, float] | None = None,
    line_width: float = 1,
) -> str:
    commands = ["q"]
    if stroke:
        red, green, blue = stroke
        commands.append(f"{line_width:.2f} w {red:.3f} {green:.3f} {blue:.3f} RG")
    if fill:
        red, green, blue = fill
        commands.append(f"{red:.3f} {green:.3f} {blue:.3f} rg")
    commands.append(f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re")
    if fill and stroke:
        commands.append("B")
    elif fill:
        commands.append("f")
    else:
        commands.append("S")
    commands.append("Q")
    return " ".join(commands)


def _build_pdf(page_commands: list[str]) -> bytes:
    stream = "\n".join(page_commands).encode("latin-1", "replace")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 4 0 R /F2 5 0 R >> >> /Contents 6 0 R >>"
        ),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >>",
        b"<< /Length "
        + str(len(stream)).encode("ascii")
        + b" >>\nstream\n"
        + stream
        + b"\nendstream",
    ]
    pdf = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: list[int] = []
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")
    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF"
        ).encode("ascii")
    )
    return bytes(pdf)


def _build_payslip_pdf(
    *,
    company_name: str,
    company_code: str,
    employee_name: str,
    employee_id: str,
    department: str,
    designation: str,
    date_of_joining: str,
    salary_effective_from: str,
    working_days: str,
    leave_taken: str,
    statement_month: str,
    earnings_rows: list[tuple[str, float, float]],
    deduction_rows: list[tuple[str, float, float]],
    net_salary_monthly: float,
    net_salary_yearly: float,
    generated_on: str,
) -> bytes:
    commands: list[str] = []
    dark = (0.12, 0.12, 0.11)
    gold = (0.88, 0.65, 0.25)
    gold_soft = (0.95, 0.92, 0.84)
    blue = (0.40, 0.47, 0.58)
    line = (0.84, 0.86, 0.90)
    white = (1.0, 1.0, 1.0)
    page_left = 38
    page_right = 557
    content_width = page_right - page_left

    commands.append(_pdf_rect(page_left, 768, content_width, 54, fill=dark))
    commands.append(_pdf_rect(page_left, 740, content_width, 28, fill=gold))
    commands.append(_pdf_text("E", 66, 790, size=14, font="F2", color=white))
    commands.append(_pdf_text("Hurema", 90, 790, size=18, font="F2", color=white))
    commands.append(_pdf_text("SALARY STATEMENT", 448, 796, size=10, color=(0.70, 0.74, 0.82)))
    commands.append(_pdf_text(statement_month, 480, 780, size=18, font="F2", color=white))
    commands.append(_pdf_text(company_name, 62, 751, size=13, font="F2", color=dark))
    commands.append(_pdf_text(company_code, 468, 751, size=11, font="F2", color=dark))

    y = 708
    left_col = page_left + 24
    right_col = 305
    commands.append(_pdf_text("EMPLOYEE NAME", left_col, y, size=10, color=blue))
    commands.append(_pdf_text(employee_name, left_col, y - 18, size=15, font="F2", color=dark))
    commands.append(_pdf_text("DATE OF JOINING", right_col, y, size=10, color=blue))
    commands.append(_pdf_text(date_of_joining, right_col, y - 18, size=13, font="F2", color=dark))

    y -= 50
    commands.append(_pdf_text("DESIGNATION", left_col, y, size=10, color=blue))
    commands.append(_pdf_text(designation, left_col, y - 18, size=13, font="F2", color=dark))
    commands.append(_pdf_text("SALARY EFFECTIVE FROM", right_col, y, size=10, color=blue))
    commands.append(_pdf_text(salary_effective_from, right_col, y - 18, size=13, font="F2", color=dark))

    y -= 50
    commands.append(_pdf_text("DEPARTMENT", left_col, y, size=10, color=blue))
    commands.append(_pdf_text(department, left_col, y - 18, size=13, font="F2", color=dark))
    commands.append(_pdf_text("WORKING DAYS", right_col, y, size=10, color=blue))
    commands.append(_pdf_text(working_days, right_col, y - 18, size=13, font="F2", color=dark))

    y -= 50
    commands.append(_pdf_text("EMPLOYEE ID", left_col, y, size=10, color=blue))
    commands.append(_pdf_text(employee_id, left_col, y - 18, size=13, font="F2", color=dark))
    commands.append(_pdf_text("LEAVE TAKEN", right_col, y, size=10, color=blue))
    commands.append(_pdf_text(leave_taken, right_col, y - 18, size=13, font="F2", color=dark))

    y -= 48
    commands.append(_pdf_line(page_left, y, page_right, y, color=line))
    y -= 28
    commands.append(_pdf_text("SALARY COMPONENTS", left_col, y, size=10, color=blue))
    commands.append(_pdf_text("MONTHLY AMOUNT", 345, y, size=10, color=blue))
    commands.append(_pdf_text("YEARLY AMOUNT", 470, y, size=10, color=blue))
    y -= 12
    commands.append(_pdf_line(left_col, y, page_right - 24, y, color=dark))
    y -= 22

    gross_earnings = round(sum(item[1] for item in earnings_rows), 2)
    total_deductions = round(sum(item[1] for item in deduction_rows), 2)

    commands.append(_pdf_text("EARNINGS", left_col, y, size=12, font="F2", color=gold))
    y -= 22
    for label, monthly_amount, yearly_amount in earnings_rows:
        commands.append(_pdf_text(label, left_col, y, size=12, color=dark))
        commands.append(_pdf_text(_currency_text(monthly_amount), 355, y, size=12, color=dark))
        commands.append(_pdf_text(_currency_text(yearly_amount), 480, y, size=12, color=dark))
        y -= 24
        commands.append(_pdf_line(left_col, y + 8, page_right - 24, y + 8, color=(0.92, 0.93, 0.95)))
    commands.append(_pdf_text("Gross earnings", left_col, y - 2, size=12, font="F2", color=dark))
    commands.append(_pdf_text(_currency_text(gross_earnings), 355, y - 2, size=12, font="F2", color=dark))
    commands.append(_pdf_text(_currency_text(gross_earnings * 12), 480, y - 2, size=12, font="F2", color=dark))

    y -= 34
    commands.append(_pdf_text("DEDUCTIONS", left_col, y, size=12, font="F2", color=gold))
    y -= 22
    for label, monthly_amount, yearly_amount in deduction_rows:
        commands.append(_pdf_text(label, left_col, y, size=12, color=dark))
        commands.append(_pdf_text(_currency_text(monthly_amount), 355, y, size=12, color=dark))
        commands.append(_pdf_text(_currency_text(yearly_amount), 480, y, size=12, color=dark))
        y -= 24
        commands.append(_pdf_line(left_col, y + 8, page_right - 24, y + 8, color=(0.92, 0.93, 0.95)))
    commands.append(_pdf_text("Total deductions", left_col, y - 2, size=12, font="F2", color=dark))
    commands.append(_pdf_text(_currency_text(total_deductions), 355, y - 2, size=12, font="F2", color=dark))
    commands.append(_pdf_text(_currency_text(total_deductions * 12), 480, y - 2, size=12, font="F2", color=dark))

    y -= 40
    commands.append(_pdf_line(left_col, y, page_right - 24, y, width=1.2, color=dark))
    y -= 30
    commands.append(_pdf_text("Net salary", left_col, y, size=15, font="F2", color=dark))
    commands.append(_pdf_text("MONTHLY", 340, y + 18, size=9, color=blue))
    commands.append(_pdf_text("YEARLY", 470, y + 18, size=9, color=blue))
    commands.append(_pdf_text(_currency_text(net_salary_monthly), 333, y, size=16, font="F2", color=gold))
    commands.append(_pdf_text(_currency_text(net_salary_yearly), 452, y, size=16, font="F2", color=dark))

    y -= 42
    commands.append(_pdf_rect(left_col, y - 18, 468, 42, fill=gold_soft))
    commands.append(_pdf_rect(left_col, y - 18, 2.5, 42, fill=gold))
    commands.append(_pdf_text("AMOUNT IN WORDS", left_col + 14, y + 8, size=9, color=blue))
    commands.append(_pdf_text(_amount_in_words(net_salary_monthly), left_col + 14, y - 8, size=12, font="F2", color=dark))

    commands.append(_pdf_line(page_left, 84, page_right, 84, color=line))
    commands.append(_pdf_text("This is a system-generated payslip and does not require a signature.", left_col, 60, size=10, color=(0.62, 0.66, 0.72)))
    commands.append(_pdf_text(f"Generated by EmPay HRMS · {generated_on}", left_col, 42, size=10, color=(0.62, 0.66, 0.72)))
    commands.append(_pdf_line(458, 42, 530, 42, color=line))
    commands.append(_pdf_text("Authorised signatory", 447, 28, size=10, color=(0.62, 0.66, 0.72)))
    return _build_pdf(commands)


def _build_payslip_pdf_themed(
    *,
    company_name: str,
    company_code: str,
    employee_name: str,
    employee_id: str,
    department: str,
    designation: str,
    date_of_joining: str,
    salary_effective_from: str,
    working_days: str,
    leave_taken: str,
    statement_month: str,
    earnings_rows: list[tuple[str, float, float]],
    deduction_rows: list[tuple[str, float, float]],
    net_salary_monthly: float,
    net_salary_yearly: float,
    generated_on: str,
) -> bytes:
    commands: list[str] = []
    ink = (0.13, 0.16, 0.24)
    purple = (0.45, 0.34, 0.53)
    purple_soft = (0.95, 0.92, 0.97)
    lilac = (0.90, 0.86, 0.94)
    gold = (0.84, 0.64, 0.28)
    muted = (0.39, 0.45, 0.56)
    line = (0.84, 0.87, 0.92)
    line_soft = (0.92, 0.94, 0.97)
    line_strong = (0.76, 0.80, 0.86)
    white = (1.0, 1.0, 1.0)
    page_left = 36
    page_right = 559
    content_width = page_right - page_left

    monthly_col_right = page_left + 392
    yearly_col_right = page_right - 24
    left_col = page_left + 24
    right_col = page_left + 282

    commands.append(_pdf_rect(page_left, 40, content_width, 782, fill=white, stroke=line, line_width=1.1))
    commands.append(_pdf_rect(page_left, 762, content_width, 60, fill=purple))
    commands.append(_pdf_rect(page_left, 734, content_width, 28, fill=lilac))
    commands.append(_pdf_rect(page_left + 24, 780, 24, 24, fill=gold))
    commands.append(_pdf_text("E", page_left + 32, 787, size=13, font="F2", color=white))
    commands.append(_pdf_text("Hurema", page_left + 58, 786, size=20, font="F2", color=white))
    commands.append(_pdf_text("SALARY STATEMENT", page_right - 116, 796, size=10, color=(0.88, 0.85, 0.93)))
    commands.append(_pdf_text_right(statement_month, page_right - 24, 780, size=16, font="F2", color=white))
    commands.append(_pdf_text(company_name, page_left + 24, 744, size=13, font="F2", color=ink))
    commands.append(_pdf_text_right(company_code, page_right - 24, 744, size=11, font="F2", color=purple))

    y = 696
    detail_rows = [
        ("EMPLOYEE NAME", employee_name, "DATE OF JOINING", date_of_joining),
        ("DESIGNATION", designation, "SALARY EFFECTIVE FROM", salary_effective_from),
        ("DEPARTMENT", department, "WORKING DAYS", working_days),
        ("EMPLOYEE ID", employee_id, "LEAVE TAKEN", leave_taken),
    ]
    for left_label, left_value, right_label, right_value in detail_rows:
        commands.append(_pdf_text(left_label, left_col, y, size=9.5, color=muted))
        commands.append(_pdf_text(left_value, left_col, y - 18, size=13, font="F2", color=ink))
        commands.append(_pdf_text(right_label, right_col, y, size=9.5, color=muted))
        commands.append(_pdf_text(right_value, right_col, y - 18, size=13, font="F2", color=ink))
        y -= 42

    commands.append(_pdf_line(page_left, y + 8, page_right, y + 8, color=line))
    commands.append(_pdf_text("SALARY COMPONENTS", left_col, y - 18, size=9.5, color=muted))
    commands.append(_pdf_text_right("MONTHLY AMOUNT", monthly_col_right, y - 18, size=9.5, color=muted))
    commands.append(_pdf_text_right("YEARLY AMOUNT", yearly_col_right, y - 18, size=9.5, color=muted))
    commands.append(_pdf_line(left_col, y - 28, page_right - 24, y - 28, color=line_strong))
    y -= 42

    gross_earnings = round(sum(item[1] for item in earnings_rows), 2)
    total_deductions = round(sum(item[1] for item in deduction_rows), 2)

    commands.append(_pdf_text("EARNINGS", left_col, y, size=12, font="F2", color=gold))
    y -= 18
    for label, monthly_amount, yearly_amount in earnings_rows:
        commands.append(_pdf_text(label, left_col, y, size=11, color=ink))
        commands.append(_pdf_text_right(_currency_text(monthly_amount), monthly_col_right, y, size=11, color=ink))
        commands.append(_pdf_text_right(_currency_text(yearly_amount), yearly_col_right, y, size=11, color=ink))
        y -= 18
        commands.append(_pdf_line(left_col, y + 6, page_right - 24, y + 6, color=line_soft))
    commands.append(_pdf_text("Gross earnings", left_col, y - 2, size=11.5, font="F2", color=ink))
    commands.append(_pdf_text_right(_currency_text(gross_earnings), monthly_col_right, y - 2, size=11.5, font="F2", color=ink))
    commands.append(_pdf_text_right(_currency_text(gross_earnings * 12), yearly_col_right, y - 2, size=11.5, font="F2", color=ink))

    y -= 24
    commands.append(_pdf_text("DEDUCTIONS", left_col, y, size=12, font="F2", color=purple))
    y -= 18
    for label, monthly_amount, yearly_amount in deduction_rows:
        commands.append(_pdf_text(label, left_col, y, size=11, color=ink))
        commands.append(_pdf_text_right(_currency_text(monthly_amount), monthly_col_right, y, size=11, color=ink))
        commands.append(_pdf_text_right(_currency_text(yearly_amount), yearly_col_right, y, size=11, color=ink))
        y -= 18
        commands.append(_pdf_line(left_col, y + 6, page_right - 24, y + 6, color=line_soft))
    commands.append(_pdf_text("Total deductions", left_col, y - 2, size=11.5, font="F2", color=ink))
    commands.append(_pdf_text_right(_currency_text(total_deductions), monthly_col_right, y - 2, size=11.5, font="F2", color=ink))
    commands.append(_pdf_text_right(_currency_text(total_deductions * 12), yearly_col_right, y - 2, size=11.5, font="F2", color=ink))

    y -= 22
    commands.append(_pdf_line(left_col, y, page_right - 24, y, width=1.2, color=purple))
    y -= 24
    commands.append(_pdf_text("Net salary", left_col, y, size=15, font="F2", color=ink))
    commands.append(_pdf_text_right("MONTHLY", monthly_col_right, y + 18, size=9, color=muted))
    commands.append(_pdf_text_right("YEARLY", yearly_col_right, y + 18, size=9, color=muted))
    commands.append(_pdf_text_right(_currency_text(net_salary_monthly), monthly_col_right, y, size=16, font="F2", color=gold))
    commands.append(_pdf_text_right(_currency_text(net_salary_yearly), yearly_col_right, y, size=16, font="F2", color=ink))

    y -= 34
    commands.append(_pdf_rect(left_col, y - 18, 470, 42, fill=purple_soft))
    commands.append(_pdf_rect(left_col, y - 18, 3, 42, fill=purple))
    commands.append(_pdf_text("AMOUNT IN WORDS", left_col + 14, y + 8, size=9, color=muted))
    commands.append(_pdf_text(_amount_in_words(net_salary_monthly), left_col + 14, y - 8, size=12, font="F2", color=ink))

    commands.append(_pdf_line(page_left, 94, page_right, 94, color=line))
    commands.append(_pdf_text("This is a system-generated payslip and does not require a signature.", left_col, 68, size=9.5, color=muted))
    commands.append(_pdf_text(f"Generated by Hurema HRMS - {generated_on}", left_col, 50, size=9.5, color=muted))
    commands.append(_pdf_line(462, 50, 536, 50, color=line))
    commands.append(_pdf_text("Authorised signatory", 444, 34, size=9.5, color=muted))
    return _build_pdf(commands)


def _build_attendance_report_pdf(*, company_name: str, report_month: str, rows: list[dict[str, Any]]) -> bytes:
    commands: list[str] = []
    ink = (0.13, 0.16, 0.24)
    purple = (0.45, 0.34, 0.53)
    muted = (0.39, 0.45, 0.56)
    lilac = (0.94, 0.92, 0.97)
    white = (1.0, 1.0, 1.0)
    line = (0.84, 0.87, 0.92)
    line_soft = (0.92, 0.94, 0.97)
    page_left = 36
    page_right = 559
    content_width = page_right - page_left
    left_col = page_left + 24
    chart_palette = [
        (0.55, 0.43, 0.72),
        (0.88, 0.63, 0.23),
        (0.36, 0.55, 0.85),
        (0.35, 0.64, 0.50),
        (0.83, 0.42, 0.36),
        (0.50, 0.56, 0.66),
    ]

    total_present = round(sum(_safe_float(row.get("presentDays")) for row in rows), 2)
    total_absent = round(sum(_safe_float(row.get("absentDays")) for row in rows), 2)
    total_payable = round(sum(_safe_float(row.get("payableDays")) for row in rows), 2)
    total_extra = round(sum(_safe_float(row.get("extraHours")) for row in rows), 2)
    department_map: dict[str, dict[str, float | str]] = {}
    for row in rows:
        label = str(row.get("department") or "General")
        entry = department_map.setdefault(label, {"label": label, "present": 0.0, "absent": 0.0, "payable": 0.0, "extra": 0.0})
        entry["present"] = float(entry["present"]) + _safe_float(row.get("presentDays"))
        entry["absent"] = float(entry["absent"]) + _safe_float(row.get("absentDays"))
        entry["payable"] = float(entry["payable"]) + _safe_float(row.get("payableDays"))
        entry["extra"] = float(entry["extra"]) + _safe_float(row.get("extraHours"))
    department_rows = sorted(department_map.values(), key=lambda item: float(item["present"]), reverse=True)[:5]

    commands.append(_pdf_rect(page_left, 36, content_width, 786, fill=white, stroke=line, line_width=1.1))
    commands.append(_pdf_rect(page_left, 762, content_width, 60, fill=purple))
    commands.append(_pdf_rect(page_left, 734, content_width, 28, fill=lilac))
    commands.append(_pdf_text("Hurema", left_col, 786, size=20, font="F2", color=white))
    commands.append(_pdf_text("ATTENDANCE REPORT", page_right - 150, 796, size=10, color=(0.89, 0.85, 0.94)))
    commands.append(_pdf_text_right(report_month, page_right - 24, 780, size=16, font="F2", color=white))
    commands.append(_pdf_text(company_name, left_col, 744, size=13, font="F2", color=ink))

    summary_y = 682
    summary_cards = [
        ("Employees", str(len(rows)), "Included in this report"),
        ("Present Days", str(int(total_present)), "Across selected employees"),
        ("Absent Days", str(int(total_absent)), "Across selected employees"),
        ("Extra Hours", f"{total_extra:.1f}", "Approved overtime hours"),
    ]
    card_width = 116
    card_gap = 12
    for index, (label, value, note) in enumerate(summary_cards):
        card_x = left_col + index * (card_width + card_gap)
        commands.append(_pdf_rect(card_x, summary_y - 34, card_width, 54, fill=lilac, stroke=line_soft))
        commands.append(_pdf_text(label.upper(), card_x + 10, summary_y + 8, size=8.5, color=muted))
        commands.append(_pdf_text(value, card_x + 10, summary_y - 8, size=16, font="F2", color=ink))
        commands.append(_pdf_text(note, card_x + 10, summary_y - 24, size=7.8, color=muted))

    chart_top = 610
    chart_bottom = 448
    left_chart_x = left_col
    left_chart_width = 250
    right_chart_x = 328
    right_chart_width = 190
    commands.append(_pdf_text("PRESENT DAYS BY DEPARTMENT", left_chart_x, chart_top, size=9.5, color=muted))
    commands.append(_pdf_text("PAYABLE DAYS BY DEPARTMENT", right_chart_x, chart_top, size=9.5, color=muted))
    commands.append(_pdf_rect(left_chart_x, chart_bottom, left_chart_width, 140, fill=(0.985, 0.982, 0.995), stroke=line_soft))
    commands.append(_pdf_rect(right_chart_x, chart_bottom, right_chart_width, 140, fill=(0.985, 0.982, 0.995), stroke=line_soft))

    max_present = max([float(item["present"]) for item in department_rows], default=1.0)
    bar_width = 30
    bar_gap = 16
    base_y = chart_bottom + 18
    usable_height = 96
    for index, item in enumerate(department_rows):
        color = chart_palette[index % len(chart_palette)]
        bar_height = usable_height * (float(item["present"]) / max_present) if max_present else 0
        x = left_chart_x + 18 + index * (bar_width + bar_gap)
        commands.append(_pdf_rect(x, base_y, bar_width, bar_height, fill=color))
        commands.append(_pdf_text_right(str(int(round(float(item["present"])))), x + bar_width, base_y + bar_height + 10, size=8.5, color=ink))
        commands.append(_pdf_text(str(item["label"])[:8], x - 2, chart_bottom + 6, size=7.5, color=muted))

    max_payable = max([float(item["payable"]) for item in department_rows], default=1.0)
    for index, item in enumerate(department_rows):
        color = chart_palette[index % len(chart_palette)]
        row_y = chart_top - 24 - index * 24
        commands.append(_pdf_text(str(item["label"])[:10], right_chart_x + 10, row_y, size=8.5, color=ink))
        commands.append(_pdf_rect(right_chart_x + 70, row_y - 8, 98, 10, fill=(0.94, 0.93, 0.97)))
        fill_width = 98 * (float(item["payable"]) / max_payable) if max_payable else 0
        commands.append(_pdf_rect(right_chart_x + 70, row_y - 8, fill_width, 10, fill=color))
        commands.append(_pdf_text_right(str(int(round(float(item["payable"])))), right_chart_x + right_chart_width - 10, row_y, size=8.5, font="F2", color=ink))

    legend_y = 418
    for index, item in enumerate(department_rows):
        color = chart_palette[index % len(chart_palette)]
        legend_x = left_col + (index % 3) * 156
        current_y = legend_y - (index // 3) * 16
        commands.append(_pdf_rect(legend_x, current_y, 8, 8, fill=color))
        commands.append(_pdf_text(str(item["label"]), legend_x + 14, current_y, size=8.5, color=muted))

    y = 374
    commands.append(_pdf_text("EMPLOYEE", left_col, y, size=9.5, color=muted))
    commands.append(_pdf_text("DEPARTMENT", 252, y, size=9.5, color=muted))
    commands.append(_pdf_text_right("PRESENT", 392, y, size=9.5, color=muted))
    commands.append(_pdf_text_right("ABSENT", 450, y, size=9.5, color=muted))
    commands.append(_pdf_text_right("PAYABLE", 508, y, size=9.5, color=muted))
    commands.append(_pdf_text_right("EXTRA", page_right - 24, y, size=9.5, color=muted))
    commands.append(_pdf_line(left_col, y - 10, page_right - 24, y - 10, color=line))
    y -= 28

    visible_rows = rows[:10]
    for row in visible_rows:
        commands.append(_pdf_text(str(row.get("employeeName", "-")), left_col, y, size=10.5, font="F2", color=ink))
        commands.append(_pdf_text(str(row.get("department", "General")), 252, y, size=10.5, color=ink))
        commands.append(_pdf_text_right(str(int(_safe_float(row.get("presentDays")))), 392, y, size=10.5, color=ink))
        commands.append(_pdf_text_right(str(int(_safe_float(row.get("absentDays")))), 450, y, size=10.5, color=ink))
        commands.append(_pdf_text_right(str(int(_safe_float(row.get("payableDays")))), 508, y, size=10.5, color=ink))
        commands.append(_pdf_text_right(f"{_safe_float(row.get('extraHours')):.1f}", page_right - 24, y, size=10.5, color=ink))
        y -= 18
        commands.append(_pdf_line(left_col, y + 8, page_right - 24, y + 8, color=line_soft))

    commands.append(_pdf_text("TOTAL", left_col, y - 2, size=11, font="F2", color=ink))
    commands.append(_pdf_text_right(str(int(total_present)), 392, y - 2, size=11, font="F2", color=ink))
    commands.append(_pdf_text_right(str(int(total_absent)), 450, y - 2, size=11, font="F2", color=ink))
    commands.append(_pdf_text_right(str(int(total_payable)), 508, y - 2, size=11, font="F2", color=ink))
    commands.append(_pdf_text_right(f"{total_extra:.1f}", page_right - 24, y - 2, size=11, font="F2", color=ink))

    if len(rows) > len(visible_rows):
        commands.append(_pdf_text(f"Showing first {len(visible_rows)} of {len(rows)} employees in this PDF summary.", left_col, 122, size=9.5, color=muted))

    commands.append(_pdf_line(page_left, 94, page_right, 94, color=line))
    commands.append(_pdf_text("This attendance report is generated from the current Hurema workspace data.", left_col, 68, size=9.5, color=muted))
    commands.append(_pdf_text(f"Generated on {datetime.now().strftime('%d %B %Y')}", left_col, 50, size=9.5, color=muted))
    return _build_pdf(commands)


async def _get_company(session: AsyncSession) -> CompanySetting:
    result = await session.execute(select(CompanySetting).limit(1))
    company = result.scalar_one_or_none()
    if company is None:
        company = CompanySetting(company_name="Hurema")
        session.add(company)
        await session.commit()
        await session.refresh(company)
    return company


async def _get_session_user(request: Request, session: AsyncSession) -> User:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Please log in to continue.")
    payload = decode_token(token)
    if not payload or "user_id" not in payload:
        raise HTTPException(status_code=401, detail="Your session has expired. Please log in again.")
    user = await session.get(User, payload["user_id"])
    if user is None or not user.is_active:
        raise HTTPException(status_code=401, detail="Your account is unavailable.")
    return user


async def _get_profile_map(session: AsyncSession, user_ids: list[int]) -> dict[int, EmployeeProfile]:
    if not user_ids:
        return {}
    result = await session.execute(select(EmployeeProfile).where(EmployeeProfile.user_id.in_(user_ids)))
    return {profile.user_id: profile for profile in result.scalars().all()}


async def _get_latest_attendance_map(session: AsyncSession, user_ids: list[int]) -> dict[int, Attendance]:
    if not user_ids:
        return {}
    result = await session.execute(
        select(Attendance)
        .where(Attendance.user_id.in_(user_ids))
        .order_by(Attendance.date.desc(), Attendance.id.desc())
    )
    latest: dict[int, Attendance] = {}
    for record in result.scalars().all():
        latest.setdefault(record.user_id, record)
    return latest


async def _serialize_user(
    session: AsyncSession,
    user: User,
    company_name: str,
    profile: EmployeeProfile | None = None,
    attendance_snapshot: Attendance | None = None,
) -> dict[str, Any]:
    if profile is None:
        profile = (
            await session.execute(select(EmployeeProfile).where(EmployeeProfile.user_id == user.id))
        ).scalar_one_or_none()
    return {
        "id": user.id,
        "fullName": _full_name(user),
        "firstName": user.first_name,
        "lastName": user.last_name,
        "employeeId": user.employee_code,
        "email": user.email,
        "role": user.role,
        "phone": profile.mobile if profile else "",
        "department": user.department,
        "designation": user.designation,
        "dateOfJoining": user.date_of_joining.isoformat() if user.date_of_joining else "",
        "location": (profile.location if profile and profile.location else user.location) or "",
        "active": user.is_active,
        "employmentStatus": "Active" if user.is_active else "Inactive",
        "address": profile.address if profile else "",
        "about": profile.about if profile else "",
        "loveAboutJob": profile.love_about_job if profile else "",
        "hobbies": profile.hobbies if profile else "",
        "skills": profile.skills if profile else "",
        "certifications": profile.certifications if profile else "",
        "profilePhoto": profile.profile_photo if profile else "",
        "emergencyContact": profile.emergency_contact if profile else "",
        "manager": profile.manager_name if profile else "",
        "companyName": company_name,
        "attendanceSnapshot": {
            "checkIn": _serialize_datetime(attendance_snapshot.check_in) if attendance_snapshot else None,
            "checkOut": _serialize_datetime(attendance_snapshot.check_out) if attendance_snapshot else None,
            "currentSessionStart": _serialize_datetime(attendance_snapshot.session_started_at) if attendance_snapshot else None,
            "pauseStartedAt": _serialize_datetime(attendance_snapshot.pause_started_at) if attendance_snapshot else None,
            "pausedMinutes": round(attendance_snapshot.paused_minutes or 0, 2) if attendance_snapshot else 0,
            "accumulatedHours": round(attendance_snapshot.accumulated_hours or 0, 2) if attendance_snapshot else 0,
            "workedHours": _worked_hours(attendance_snapshot, datetime.now().astimezone()) if attendance_snapshot else 0,
            "extraHours": round(attendance_snapshot.extra_hours or 0, 2) if attendance_snapshot else 0,
            "status": attendance_snapshot.status if attendance_snapshot else "No Record",
        },
    }


async def _log_action(
    session: AsyncSession,
    actor_id: int | None,
    action: str,
    target_type: str,
    target_id: str,
) -> None:
    session.add(AuditLog(actor_id=actor_id, action=action, target_type=target_type, target_id=target_id))
    await session.commit()


async def _get_or_create_salary_structure(session: AsyncSession, user_id: int) -> SalaryStructure:
    result = await session.execute(select(SalaryStructure).where(SalaryStructure.user_id == user_id))
    structure = result.scalar_one_or_none()
    if structure is None:
        structure = SalaryStructure(user_id=user_id)
        session.add(structure)
        await session.commit()
        await session.refresh(structure)
    return structure


def _salary_info(structure: SalaryStructure) -> dict[str, Any]:
    month_wage = round(structure.month_wage, 2)
    items = [
        ("basicSalary", structure.basic_percentage, "Primary fixed component."),
        ("houseRentAllowance", structure.hra_percentage, "House rent allowance."),
        ("standardAllowance", structure.standard_allowance_percentage, "Standard fixed allowance."),
        ("performanceBonus", structure.performance_bonus_percentage, "Performance-linked bonus."),
        ("leaveTravelAllowance", structure.leave_travel_allowance_percentage, "Leave travel allowance."),
        ("fixedAllowance", structure.fixed_allowance_percentage, "Remaining fixed allowance."),
    ]
    breakdown: dict[str, dict[str, Any]] = {}
    for key, percentage, note in items:
        breakdown[key] = {
            "percentage": round(percentage, 2),
            "amount": round(month_wage * percentage / 100, 2),
            "note": note,
        }
    basic_amount = breakdown["basicSalary"]["amount"]
    return {
        "monthWage": month_wage,
        "yearWage": round(month_wage * 12, 2),
        "workingDaysPerWeek": structure.working_days_per_week,
        "breakHours": structure.break_hours,
        "breakdown": breakdown,
        "providentFund": {
            "employeePercentage": round(structure.employee_pf_percentage, 2),
            "employeeAmount": round(basic_amount * structure.employee_pf_percentage / 100, 2),
            "employerPercentage": round(structure.employer_pf_percentage, 2),
            "employerAmount": round(basic_amount * structure.employer_pf_percentage / 100, 2),
        },
        "tax": {
            "professionalTax": round(structure.professional_tax, 2),
            "otherDeduction": round(structure.other_deduction, 2),
        },
    }


async def _attendance_records_for_range(
    session: AsyncSession,
    user_id: int,
    start_date: date,
    end_date: date,
    specific_day: date | None = None,
) -> list[Attendance]:
    stmt = (
        select(Attendance)
        .where(Attendance.user_id == user_id, Attendance.date >= start_date, Attendance.date <= end_date)
        .order_by(Attendance.date.desc())
    )
    if specific_day:
        stmt = select(Attendance).where(Attendance.user_id == user_id, Attendance.date == specific_day).order_by(Attendance.id.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


async def _approved_leave_days(session: AsyncSession, user_id: int, start_date: date, end_date: date) -> int:
    result = await session.execute(
        select(LeaveRequest).where(
            LeaveRequest.user_id == user_id,
            LeaveRequest.status == "Approved",
            LeaveRequest.end_date >= start_date,
            LeaveRequest.start_date <= end_date,
        )
    )
    total = 0
    for leave in result.scalars().all():
        overlap_start = max(start_date, leave.start_date)
        overlap_end = min(end_date, leave.end_date)
        total += (overlap_end - overlap_start).days + 1
    return total


async def _attendance_payload(
    session: AsyncSession,
    target_user: User,
    month: str | None,
    day: str | None,
) -> dict[str, Any]:
    current_time = datetime.now().astimezone()
    start_date, end_date = _month_bounds(month)
    specific_day = date.fromisoformat(day) if day else None
    records = await _attendance_records_for_range(session, target_user.id, start_date, end_date, specific_day)
    approved_leave_days = await _approved_leave_days(
        session,
        target_user.id,
        specific_day or start_date,
        specific_day or end_date,
    )
    present_days = len({record.date for record in records if record.check_in or record.session_started_at})
    extra_hours = round(sum(record.extra_hours or 0 for record in records), 2)
    worked_hours = round(sum(_worked_hours(record, current_time) for record in records), 2)
    range_start = specific_day or start_date
    range_end = specific_day or end_date
    expected_days = 1 if specific_day else _business_days(range_start, range_end)
    payable_days = min(present_days + approved_leave_days, expected_days)
    absent_days = max(expected_days - payable_days, 0)
    company = await _get_company(session)
    serialized_user = await _serialize_user(session, target_user, company.company_name)
    return {
        "employee": serialized_user,
        "records": [
            {
                "id": record.id,
                "employeeId": target_user.id,
                "date": record.date.isoformat(),
                "checkIn": _serialize_datetime(record.check_in),
                "checkOut": _serialize_datetime(record.check_out),
                "currentSessionStart": _serialize_datetime(record.session_started_at),
                "pauseStartedAt": _serialize_datetime(record.pause_started_at),
                "pausedMinutes": round(record.paused_minutes or 0, 2),
                "accumulatedHours": round(record.accumulated_hours or 0, 2),
                "workedHours": _worked_hours(record, current_time),
                "extraHours": round(record.extra_hours or 0, 2),
                "status": record.status,
            }
            for record in records
        ],
        "summary": {
            "presentDays": present_days,
            "absentDays": absent_days,
            "payableDays": payable_days,
            "workedHours": worked_hours,
            "extraHours": extra_hours,
        },
    }


async def _payrun_payloads(session: AsyncSession, month: str | None = None, status: str | None = None) -> list[dict[str, Any]]:
    stmt = select(Payroll).order_by(Payroll.year.desc(), Payroll.month.desc(), Payroll.generated_at.desc())
    if month:
        year, month_number = [int(part) for part in month.split("-", 1)]
        stmt = stmt.where(Payroll.year == year, Payroll.month == month_number)
    result = await session.execute(stmt)
    payrolls = result.scalars().all()
    grouped: dict[tuple[int, int], list[Payroll]] = {}
    for payroll in payrolls:
        grouped.setdefault((payroll.year, payroll.month), []).append(payroll)

    payloads: list[dict[str, Any]] = []
    for (year, month_number), records in grouped.items():
        payrun_status = "Locked"
        if status and payrun_status != status:
            continue
        payloads.append(
            {
                "id": f"{year}-{month_number:02d}",
                "month": f"{year}-{month_number:02d}",
                "status": payrun_status,
                "generatedAt": max(record.generated_at for record in records).isoformat() if records else None,
                "records": [
                    {
                        "id": record.id,
                        "employeeId": record.user_id,
                        "grossSalary": round(record.gross_salary, 2),
                        "netSalary": round(record.net_salary, 2),
                    }
                    for record in records
                ],
            }
        )
    return payloads


async def _serialize_leaves(session: AsyncSession, leaves: list[LeaveRequest]) -> list[dict[str, Any]]:
    users = {user.id: user for user in (await session.execute(select(User))).scalars().all()}
    leave_type_map = {leave_type.name: leave_type for leave_type in (await session.execute(select(LeaveType))).scalars().all()}
    serialized = []
    for leave in leaves:
        employee = users.get(leave.user_id)
        if employee is None:
            continue
        serialized.append(
            {
                "id": leave.id,
                "employeeId": leave.user_id,
                "employeeName": _full_name(employee),
                "leaveTypeId": leave_type_map.get(leave.leave_type).id if leave_type_map.get(leave.leave_type) else None,
                "leaveTypeName": leave.leave_type,
                "startDate": leave.start_date.isoformat(),
                "endDate": leave.end_date.isoformat(),
                "days": leave.days_requested,
                "status": leave.status,
                "reason": leave.reason,
            }
        )
    return serialized


@router.get("/auth/me")
async def auth_me(request: Request, session: AsyncSession = Depends(get_db)):
    user = await _get_session_user(request, session)
    token = request.cookies.get(SESSION_COOKIE)
    payload = decode_token(token) if token else None
    company = await _get_company(session)
    latest_attendance = (await _get_latest_attendance_map(session, [user.id])).get(user.id)
    profile = (await _get_profile_map(session, [user.id])).get(user.id)
    return {
        "user": await _serialize_user(session, user, company.company_name, profile=profile, attendance_snapshot=latest_attendance),
        "role": user.role,
        "csrfToken": str(payload.get("csrf", "")) if payload else "",
        "serverNow": datetime.now().astimezone().isoformat(),
        "settings": {"companyName": company.company_name, "companyLogo": company.company_logo or ""},
        "permissions": _role_permissions(user.role),
    }


@router.post("/auth/login")
async def login(payload: dict[str, Any], request: Request, session: AsyncSession = Depends(get_db)):
    _enforce_auth_rate_limit(request, "login")
    identifier = str(payload.get("identifier", payload.get("email", ""))).strip()
    if not identifier:
        _register_attempt(request, "login")
        raise HTTPException(status_code=401, detail="Invalid email, login ID, or password.")
    user = (
        await session.execute(
            select(User).where(
                or_(
                    User.email == identifier.lower(),
                    User.employee_code == identifier.upper(),
                )
            )
        )
    ).scalar_one_or_none()
    if user is None or not verify_password(str(payload.get("password", "")), user.hashed_password):
        _register_attempt(request, "login")
        raise HTTPException(status_code=401, detail="Invalid email, login ID, or password.")
    csrf_token = secrets.token_urlsafe(32)
    token = create_access_token({"sub": user.email, "user_id": user.id, "role": user.role, "csrf": csrf_token})
    _clear_attempts(request, "login")
    await _log_action(session, user.id, "Logged in", "auth", user.employee_code)
    response = JSONResponse({"ok": True, "csrfToken": csrf_token})
    _set_auth_cookies(request, response, token)
    return response


@router.post("/auth/signup")
async def signup(payload: dict[str, Any], request: Request, session: AsyncSession = Depends(get_db)):
    _enforce_auth_rate_limit(request, "signup")
    if str(payload.get("password", "")) != str(payload.get("confirmPassword", "")):
        _register_attempt(request, "signup")
        raise HTTPException(status_code=400, detail="Passwords do not match.")
    _validate_password(str(payload.get("password", "")))
    full_name = str(payload.get("fullName", "")).strip()
    first_name, last_name = _split_name(full_name)
    email = str(payload.get("email", "")).strip().lower()
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        _register_attempt(request, "signup")
        raise HTTPException(status_code=400, detail="A user with this email already exists.")

    company = await _get_company(session)
    company_name = str(payload.get("companyName", "")).strip()
    if company_name:
        company.company_name = company_name
    if payload.get("companyLogo") is not None:
        company.company_logo = _validate_company_logo(str(payload.get("companyLogo", "")))

    user = User(
        employee_code=await generate_employee_code(session, first_name, last_name, date.today().year),
        first_name=first_name,
        last_name=last_name,
        email=email,
        hashed_password=hash_password(str(payload.get("password", ""))),
        role="Admin",
        department="Operations",
        designation="Administrator",
        date_of_joining=date.today(),
        location="Bengaluru",
        is_active=True,
        is_first_login=False,
    )
    session.add(user)
    await session.flush()
    session.add(
        EmployeeProfile(
            user_id=user.id,
            mobile=str(payload.get("phone", "")).strip(),
            location="Bengaluru",
            basic_salary=90000.0,
            manager_name="",
        )
    )
    leave_types = (await session.execute(select(LeaveType))).scalars().all()
    for leave_type in leave_types:
        session.add(LeaveBalance(user_id=user.id, leave_type_id=leave_type.id, balance=leave_type.default_balance))
    session.add(SalaryStructure(user_id=user.id, month_wage=90000.0))
    await session.commit()

    csrf_token = secrets.token_urlsafe(32)
    token = create_access_token({"sub": user.email, "user_id": user.id, "role": user.role, "csrf": csrf_token})
    _clear_attempts(request, "signup")
    await _log_action(session, user.id, "Created admin workspace account", "user", user.employee_code)
    response = JSONResponse({"ok": True, "csrfToken": csrf_token})
    _set_auth_cookies(request, response, token)
    return response


@router.post("/auth/logout")
async def logout(request: Request, x_csrf_token: str | None = Header(default=None)):
    _require_csrf(request, x_csrf_token)
    response = JSONResponse({"ok": True})
    _clear_auth_cookies(request, response)
    return response


@router.post("/auth/change-password")
async def change_password(
    payload: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_csrf_token: str | None = Header(default=None),
):
    _require_csrf(request, x_csrf_token)
    current_user = await _get_session_user(request, session)
    current_password = str(payload.get("currentPassword", ""))
    new_password = str(payload.get("newPassword", ""))
    confirm_password = str(payload.get("confirmPassword", ""))
    if not verify_password(current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect.")
    if new_password != confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirmation do not match.")
    _validate_password(new_password)
    current_user.hashed_password = hash_password(new_password)
    await session.commit()
    await _log_action(session, current_user.id, "Changed password", "auth", current_user.employee_code)
    return {"ok": True}


@router.get("/employees")
async def list_employees(
    request: Request,
    includeAdmins: bool = Query(False),
    session: AsyncSession = Depends(get_db),
):
    current_user = await _get_session_user(request, session)
    stmt = select(User).options(joinedload(User.profile)).order_by(User.first_name.asc(), User.last_name.asc())
    if not includeAdmins:
        stmt = stmt.where(User.role != "Admin")
    result = await session.execute(stmt)
    users = result.scalars().all()
    if current_user.role == "Employee":
        users = [user for user in users if user.id == current_user.id]
    company = await _get_company(session)
    latest_map = await _get_latest_attendance_map(session, [user.id for user in users])
    employees = [
        await _serialize_user(
            session,
            user,
            company.company_name,
            profile=user.profile,
            attendance_snapshot=latest_map.get(user.id),
        )
        for user in users
    ]
    return {"employees": employees}


@router.post("/employees")
async def create_employee(
    payload: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_csrf_token: str | None = Header(default=None),
):
    _require_csrf(request, x_csrf_token)
    current_user = await _get_session_user(request, session)
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Only admins can create users.")
    _validate_password(str(payload.get("password", "")))
    full_name = str(payload.get("fullName", "")).strip()
    first_name, last_name = _split_name(full_name)
    email = str(payload.get("email", "")).strip().lower()
    joining_date = date.fromisoformat(str(payload["dateOfJoining"])) if payload.get("dateOfJoining") else date.today()
    existing = await session.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="A user with this email already exists.")
    employee_code = await generate_employee_code(
        session,
        first_name,
        last_name,
        joining_date.year,
    )
    user = User(
        employee_code=employee_code,
        first_name=first_name,
        last_name=last_name,
        email=email,
        hashed_password=hash_password(str(payload.get("password", ""))),
        role=_validate_role(str(payload.get("role", "Employee"))),
        department=str(payload.get("department", "General")) or "General",
        designation=str(payload.get("designation", "Team Member")) or "Team Member",
        date_of_joining=joining_date,
        location=str(payload.get("location", "Bengaluru")).strip() or "Bengaluru",
        is_active=True,
        is_first_login=False,
        created_by=current_user.id,
    )
    session.add(user)
    await session.flush()
    session.add(
        EmployeeProfile(
            user_id=user.id,
            mobile=str(payload.get("phone", "")).strip(),
            location=str(payload.get("location", "Bengaluru")).strip() or "Bengaluru",
            basic_salary=_safe_float(payload.get("monthWage"), 50000.0),
            manager_name=_full_name(current_user),
            manager_id=current_user.id,
        )
    )
    leave_types = (await session.execute(select(LeaveType))).scalars().all()
    for leave_type in leave_types:
        session.add(LeaveBalance(user_id=user.id, leave_type_id=leave_type.id, balance=leave_type.default_balance))
    session.add(SalaryStructure(user_id=user.id, month_wage=_safe_float(payload.get("monthWage"), 50000.0)))
    await session.commit()

    company = await _get_company(session)
    credentials_sent = await EmailService.send_credentials(
        email=user.email,
        employee_code=user.employee_code,
        temporary_password=str(payload.get("password", "")),
        company_name=company.company_name,
    )
    session.add(EmailLog(user_id=user.id, email=user.email, credential_sent=credentials_sent))
    await session.commit()

    await _log_action(session, current_user.id, f"Created {user.role}", "user", user.employee_code)
    return {
        "ok": True,
        "emailSent": credentials_sent,
        "employeeId": user.employee_code,
        "message": "User created and credentials emailed." if credentials_sent else "User created but credential email could not be sent.",
    }


@router.put("/employees/{user_id}")
async def update_employee(
    user_id: int,
    payload: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_csrf_token: str | None = Header(default=None),
):
    _require_csrf(request, x_csrf_token)
    current_user = await _get_session_user(request, session)
    target_user = await session.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if current_user.role != "Admin" and current_user.id != target_user.id and current_user.role != "HR Officer":
        raise HTTPException(status_code=403, detail="You do not have permission to update this user.")

    profile = (
        await session.execute(select(EmployeeProfile).where(EmployeeProfile.user_id == target_user.id))
    ).scalar_one_or_none()
    if profile is None:
        profile = EmployeeProfile(user_id=target_user.id, basic_salary=0.0)
        session.add(profile)
        await session.flush()

    if "fullName" in payload and payload["fullName"]:
        first_name, last_name = _split_name(str(payload["fullName"]))
        target_user.first_name = first_name
        target_user.last_name = last_name
    if "email" in payload and payload["email"]:
        next_email = str(payload["email"]).strip().lower()
        if next_email != target_user.email:
            existing = (
                await session.execute(select(User).where(User.email == next_email, User.id != target_user.id))
            ).scalar_one_or_none()
            if existing is not None:
                raise HTTPException(status_code=400, detail="A user with this email already exists.")
        target_user.email = next_email
    if current_user.role in {"Admin", "HR Officer"}:
        target_user.department = str(payload.get("department", target_user.department))
        target_user.designation = str(payload.get("designation", target_user.designation))
        if payload.get("role") and current_user.role == "Admin":
            target_user.role = _validate_role(str(payload["role"]))
        if "active" in payload and current_user.role == "Admin":
            active = payload["active"]
            target_user.is_active = active if isinstance(active, bool) else str(active).lower() == "true"
        if payload.get("dateOfJoining"):
            target_user.date_of_joining = date.fromisoformat(str(payload["dateOfJoining"]))
    if payload.get("phone") is not None:
        profile.mobile = str(payload.get("phone", ""))
    if payload.get("location") is not None:
        profile.location = str(payload.get("location", ""))
        target_user.location = str(payload.get("location", "")) or target_user.location
    if payload.get("address") is not None:
        profile.address = str(payload.get("address", ""))
    if payload.get("about") is not None:
        profile.about = str(payload.get("about", ""))
    if payload.get("loveAboutJob") is not None:
        profile.love_about_job = str(payload.get("loveAboutJob", ""))
    if payload.get("hobbies") is not None:
        profile.hobbies = str(payload.get("hobbies", ""))
    if payload.get("skills") is not None:
        profile.skills = str(payload.get("skills", ""))
    if payload.get("certifications") is not None:
        profile.certifications = str(payload.get("certifications", ""))
    if payload.get("profilePhoto") is not None:
        profile.profile_photo = _validate_profile_photo(str(payload.get("profilePhoto", "")))
    if payload.get("emergencyContact") is not None:
        profile.emergency_contact = str(payload.get("emergencyContact", ""))
    if payload.get("manager") is not None:
        profile.manager_name = str(payload.get("manager", ""))
    if current_user.role == "Admin" and payload.get("companyLogo") is not None:
        company = await _get_company(session)
        company.company_logo = _validate_company_logo(str(payload.get("companyLogo", "")))

    await session.commit()
    await _log_action(session, current_user.id, "Updated user profile", "user", target_user.employee_code)
    return {"ok": True}


@router.delete("/employees/{user_id}")
async def delete_employee(
    user_id: int,
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_csrf_token: str | None = Header(default=None),
):
    _require_csrf(request, x_csrf_token)
    current_user = await _get_session_user(request, session)
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Only admins can delete users.")
    target_user = await session.get(User, user_id)
    if target_user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    if target_user.role == "Admin":
        raise HTTPException(status_code=400, detail="Admin users cannot be deleted.")
    if target_user.id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account.")

    await session.execute(update(User).where(User.created_by == target_user.id).values(created_by=None))
    await session.execute(update(EmployeeProfile).where(EmployeeProfile.manager_id == target_user.id).values(manager_id=None))
    await session.execute(update(LeaveRequest).where(LeaveRequest.approved_by == target_user.id).values(approved_by=None))
    await session.execute(update(Payroll).where(Payroll.generated_by == target_user.id).values(generated_by=current_user.id))
    await session.execute(update(AuditLog).where(AuditLog.actor_id == target_user.id).values(actor_id=None))

    payroll_ids = (
        await session.execute(select(Payroll.id).where(Payroll.user_id == target_user.id))
    ).scalars().all()

    await session.execute(delete(Attendance).where(Attendance.user_id == target_user.id))
    await session.execute(delete(LeaveBalance).where(LeaveBalance.user_id == target_user.id))
    await session.execute(delete(LeaveRequest).where(LeaveRequest.user_id == target_user.id))
    if payroll_ids:
        await session.execute(delete(Payslip).where(Payslip.payroll_id.in_(payroll_ids)))
    await session.execute(delete(Payslip).where(Payslip.user_id == target_user.id))
    await session.execute(delete(Payroll).where(Payroll.user_id == target_user.id))
    await session.execute(delete(EmailLog).where(EmailLog.user_id == target_user.id))
    await session.execute(delete(SalaryStructure).where(SalaryStructure.user_id == target_user.id))
    await session.execute(delete(EmployeeProfile).where(EmployeeProfile.user_id == target_user.id))
    await session.execute(delete(User).where(User.id == target_user.id))

    await session.commit()
    await _log_action(session, current_user.id, "Deleted user", "user", target_user.employee_code)
    return {"ok": True}


@router.get("/dashboard")
async def dashboard(
    request: Request,
    month: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
):
    current_user = await _get_session_user(request, session)
    company = await _get_company(session)
    current_month_key = month or date.today().strftime("%Y-%m")
    current_year, current_month_number = _month_parts(current_month_key)
    current_start, current_end = _month_bounds(current_month_key)
    business_days_current = _business_days(current_start, current_end)
    month_series = _month_window(current_month_key, 5)
    earliest_month_start = month_series[0]["start"]
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_days = [week_start + timedelta(days=index) for index in range(5)]

    all_users = (await session.execute(select(User).order_by(User.first_name.asc(), User.last_name.asc()))).scalars().all()
    active_users = [user for user in all_users if user.is_active]
    active_staff = [user for user in active_users if user.role != "Admin"]
    staff_ids = [user.id for user in active_staff]

    payrolls = (
        await session.execute(select(Payroll).where(Payroll.user_id.in_(staff_ids)).order_by(Payroll.year.asc(), Payroll.month.asc()))
    ).scalars().all()
    leaves = (
        await session.execute(select(LeaveRequest).where(LeaveRequest.user_id.in_(staff_ids)).order_by(LeaveRequest.created_at.desc()))
    ).scalars().all()
    attendance_records = (
        await session.execute(
            select(Attendance).where(
                Attendance.user_id.in_(staff_ids),
                Attendance.date >= min(earliest_month_start, week_start),
                Attendance.date <= current_end,
            )
        )
    ).scalars().all()
    leave_balances = (
        await session.execute(select(LeaveBalance).where(LeaveBalance.user_id.in_(staff_ids)))
    ).scalars().all()
    leave_types = (await session.execute(select(LeaveType).order_by(LeaveType.name.asc()))).scalars().all()

    department_users: dict[str, list[User]] = defaultdict(list)
    for user in active_staff:
        department_users[user.department].append(user)

    payrolls_by_month: dict[str, list[Payroll]] = defaultdict(list)
    payrolls_by_user: dict[int, list[Payroll]] = defaultdict(list)
    for payroll in payrolls:
        key = _month_key(payroll.year, payroll.month)
        payrolls_by_month[key].append(payroll)
        payrolls_by_user[payroll.user_id].append(payroll)

    attendance_by_user_month: dict[int, list[Attendance]] = defaultdict(list)
    attendance_lookup_by_day: dict[tuple[int, date], Attendance] = {}
    for record in attendance_records:
        if current_start <= record.date <= current_end:
            attendance_by_user_month[record.user_id].append(record)
        attendance_lookup_by_day[(record.user_id, record.date)] = record

    approved_leave_days_by_user: dict[int, int] = defaultdict(int)
    leave_type_days: dict[str, int] = defaultdict(int)
    leave_status_counts: dict[str, int] = defaultdict(int)
    approved_leave_week_buckets = [0, 0, 0, 0]
    for leave in leaves:
        overlap = _overlap_days(leave.start_date, leave.end_date, current_start, current_end)
        if overlap <= 0:
            continue
        leave_status_counts[leave.status] += overlap
        leave_type_days[leave.leave_type] += overlap
        if leave.status == "Approved":
            approved_leave_days_by_user[leave.user_id] += overlap
            created_day = leave.created_at.date() if leave.created_at else current_start
            if current_start <= created_day <= current_end:
                bucket = min((created_day.day - 1) // 7, 3)
                approved_leave_week_buckets[bucket] += 1

    balance_type_names = {leave_type.id: leave_type.name for leave_type in leave_types}
    leave_balance_by_user: dict[int, list[LeaveBalance]] = defaultdict(list)
    for balance in leave_balances:
        leave_balance_by_user[balance.user_id].append(balance)

    def user_month_summary(user: User) -> dict[str, float]:
        present_days = len({record.date for record in attendance_by_user_month.get(user.id, []) if record.check_in})
        leave_days = approved_leave_days_by_user.get(user.id, 0)
        payable_days = min(present_days + leave_days, business_days_current)
        absent_days = max(business_days_current - payable_days, 0)
        return {
            "presentDays": present_days,
            "leaveDays": leave_days,
            "payableDays": payable_days,
            "absentDays": absent_days,
        }

    attendance_rate_by_department = []
    absenteeism_rate_by_department = []
    headcount_by_department = []
    for department, users in department_users.items():
        expected = business_days_current * len(users)
        payable_total = 0
        absent_total = 0
        for user in users:
            summary = user_month_summary(user)
            payable_total += summary["payableDays"]
            absent_total += summary["absentDays"]
        attendance_rate = round(_safe_ratio(payable_total, expected) * 100, 1)
        absenteeism_rate = round(_safe_ratio(absent_total, expected) * 100, 1)
        headcount_by_department.append({"label": department, "value": len(users)})
        attendance_rate_by_department.append({"label": department, "value": attendance_rate})
        absenteeism_rate_by_department.append({"label": department, "value": absenteeism_rate})

    current_payrolls = payrolls_by_month.get(current_month_key, [])
    total_gross_current = round(sum(item.gross_salary for item in current_payrolls), 2)
    total_net_current = round(sum(item.net_salary for item in current_payrolls), 2)
    total_deductions_current = round(
        sum(item.pf_contribution + item.professional_tax + item.other_deductions for item in current_payrolls),
        2,
    )

    payroll_trend = []
    gross_vs_net_trend = {"gross": [], "net": []}
    headcount_growth = []
    for window in month_series:
        month_payrolls = payrolls_by_month.get(window["key"], [])
        month_gross = round(sum(item.gross_salary for item in month_payrolls), 2)
        month_net = round(sum(item.net_salary for item in month_payrolls), 2)
        payroll_trend.append({"label": window["label"], "value": month_gross})
        gross_vs_net_trend["gross"].append({"label": window["label"], "value": month_gross})
        gross_vs_net_trend["net"].append({"label": window["label"], "value": month_net})
        headcount_growth.append(
            {
                "label": window["label"],
                "value": sum(1 for user in active_staff if user.date_of_joining and user.date_of_joining <= window["end"]),
            }
        )

    leave_type_distribution = []
    total_leave_type_days = sum(leave_type_days.values())
    palette = ["#e3a641", "#58a47b", "#5d84cf", "#d96561", "#9d93cf", "#a7a39d"]
    for index, (label, value) in enumerate(sorted(leave_type_days.items(), key=lambda item: item[1], reverse=True)):
        leave_type_distribution.append(
            {
                "label": label,
                "value": value,
                "display": _percent_text(_safe_ratio(value, total_leave_type_days) * 100),
                "color": palette[index % len(palette)],
            }
        )

    leave_status_distribution = []
    status_colors = {"Approved": "#58a47b", "Pending": "#e3a641", "Rejected": "#d96561", "Cancelled": "#8d94a5"}
    total_leave_status_days = sum(leave_status_counts.values())
    for label in ["Approved", "Pending", "Rejected", "Cancelled"]:
        value = leave_status_counts.get(label, 0)
        if value:
            leave_status_distribution.append(
                {
                    "label": label,
                    "value": value,
                    "display": _percent_text(_safe_ratio(value, total_leave_status_days) * 100),
                    "color": status_colors.get(label, "#8d94a5"),
                }
            )

    current_week_attendance = []
    for day_value in week_days:
        count = sum(1 for record in attendance_records if record.date == day_value and record.check_in)
        current_week_attendance.append({"label": day_value.strftime("%a"), "value": count})

    late_checkins_week = sum(
        1
        for record in attendance_records
        if week_start <= record.date <= week_start + timedelta(days=4)
        and record.check_in
        and record.check_in.time() > time(9, 5)
    )

    new_profiles_this_month = sum(
        1 for user in active_staff if user.created_at and current_start <= user.created_at.date() <= current_end
    )
    pending_leaves_count = sum(1 for leave in leaves if leave.status == "Pending")
    leave_balance_total = round(sum(balance.balance for balance in leave_balances), 2)

    payroll_by_department: dict[str, float] = defaultdict(float)
    for payroll in current_payrolls:
        employee = next((user for user in active_staff if user.id == payroll.user_id), None)
        if employee is None:
            continue
        payroll_by_department[employee.department] += payroll.net_salary

    if current_user.role == "Admin":
        avg_attendance = round(
            _safe_ratio(
                sum(user_month_summary(user)["payableDays"] for user in active_staff),
                max(len(active_staff) * business_days_current, 1),
            )
            * 100,
            1,
        )
        return {
            "variant": "admin",
            "cards": [
                {"label": "Total employees", "value": str(len(active_staff)), "note": f"+{new_profiles_this_month} this month", "tone": "accent"},
                {"label": "Avg attendance", "value": _percent_text(avg_attendance), "note": f"{business_days_current} working days in view", "tone": "success"},
                {"label": "Monthly payroll", "value": _compact_currency_text(total_gross_current), "note": f"{_month_label(current_month_key)}", "tone": "accent"},
                {"label": "Pending leaves", "value": str(pending_leaves_count), "note": f"{pending_leaves_count} need review", "tone": "warning"},
            ],
            "headcountByDepartment": [
                {**item, "color": palette[index % len(palette)], "display": str(item["value"])}
                for index, item in enumerate(sorted(headcount_by_department, key=lambda item: item["value"], reverse=True))
            ],
            "leaveTypeDistribution": leave_type_distribution,
            "monthlyPayrollTrend": payroll_trend,
            "attendanceRateByDepartment": [
                {**item, "color": palette[index % len(palette)], "display": _percent_text(item["value"])}
                for index, item in enumerate(sorted(attendance_rate_by_department, key=lambda item: item["value"], reverse=True))
            ],
        }

    if current_user.role == "HR Officer":
        return {
            "variant": "hr",
            "cards": [
                {"label": "Active employees", "value": str(len(active_staff)), "note": f"{pending_leaves_count} leave requests pending", "tone": "accent"},
                {"label": "Late check-ins", "value": str(late_checkins_week), "note": "this week", "tone": "danger"},
                {"label": "Leaves allocated", "value": f"{int(round(leave_balance_total)):,}", "note": "days across active staff", "tone": "accent"},
                {"label": "New profiles", "value": str(new_profiles_this_month), "note": "created this month", "tone": "success"},
            ],
            "weeklyAttendance": current_week_attendance,
            "leaveStatusBreakdown": leave_status_distribution,
            "absenteeismRateByDepartment": [
                {**item, "color": palette[index % len(palette)], "display": _percent_text(item["value"])}
                for index, item in enumerate(sorted(absenteeism_rate_by_department, key=lambda item: item["value"], reverse=True))
            ],
            "headcountGrowth": headcount_growth,
        }

    if current_user.role == "Payroll Officer":
        deduction_items = [
            {
                "label": "PF",
                "value": round(sum(item.pf_contribution for item in current_payrolls), 2),
                "display": _compact_currency_text(sum(item.pf_contribution for item in current_payrolls)),
                "color": "#5d84cf",
            },
            {
                "label": "PT",
                "value": round(sum(item.professional_tax for item in current_payrolls), 2),
                "display": _compact_currency_text(sum(item.professional_tax for item in current_payrolls)),
                "color": "#e3a641",
            },
            {
                "label": "Other",
                "value": round(sum(item.other_deductions for item in current_payrolls), 2),
                "display": _compact_currency_text(sum(item.other_deductions for item in current_payrolls)),
                "color": "#d96561",
            },
        ]
        return {
            "variant": "payroll",
            "cards": [
                {"label": "Payslips generated", "value": str(len(current_payrolls)), "note": "100% processed" if current_payrolls else "No payslips generated", "tone": "success"},
                {"label": "Gross payroll", "value": _compact_currency_text(total_gross_current), "note": "before deductions", "tone": "accent"},
                {"label": "Total deductions", "value": _compact_currency_text(total_deductions_current), "note": "PF + PT + other", "tone": "warning"},
                {"label": "Net disbursed", "value": _compact_currency_text(total_net_current), "note": f"for {_month_label(current_month_key)}", "tone": "success"},
            ],
            "deductionBreakdown": deduction_items,
            "netPayrollByDepartment": [
                {**{"label": key, "value": round(value, 2), "display": _compact_currency_text(value), "color": palette[index % len(palette)]}}
                for index, (key, value) in enumerate(sorted(payroll_by_department.items(), key=lambda item: item[1], reverse=True))
            ],
            "grossVsNetTrend": gross_vs_net_trend,
            "timeOffApprovalsByWeek": [
                {"label": f"Week {index + 1}", "value": value, "color": palette[1 if index != 2 else 0]}
                for index, value in enumerate(approved_leave_week_buckets)
            ],
        }

    attendance = await _attendance_payload(session, current_user, current_month_key, None)
    employee_balances = leave_balance_by_user.get(current_user.id, [])
    employee_balance_items = [
        {
            "label": balance_type_names.get(balance.leave_type_id, "Leave"),
            "value": round(balance.balance, 2),
            "display": f"{round(balance.balance, 1)} days",
            "color": palette[index % len(palette)],
        }
        for index, balance in enumerate(sorted(employee_balances, key=lambda item: item.balance, reverse=True))
    ]
    latest_employee_payrolls = sorted(
        payrolls_by_user.get(current_user.id, []),
        key=lambda item: (item.year, item.month),
    )
    latest_employee_payroll = latest_employee_payrolls[-1] if latest_employee_payrolls else None
    structure = (
        await session.execute(select(SalaryStructure).where(SalaryStructure.user_id == current_user.id))
    ).scalar_one_or_none()
    salary_info = _salary_info(structure) if structure else None
    salary_breakdown = []
    if salary_info:
        allowance_amount = round(
            salary_info["breakdown"]["standardAllowance"]["amount"]
            + salary_info["breakdown"]["leaveTravelAllowance"]["amount"]
            + salary_info["breakdown"]["fixedAllowance"]["amount"],
            2,
        )
        salary_breakdown = [
            {"label": "Basic", "value": salary_info["breakdown"]["basicSalary"]["amount"], "color": "#5d84cf"},
            {"label": "HRA", "value": salary_info["breakdown"]["houseRentAllowance"]["amount"], "color": "#e3a641"},
            {"label": "Allowance", "value": allowance_amount, "color": "#58a47b"},
            {"label": "PF", "value": latest_employee_payroll.pf_contribution if latest_employee_payroll else salary_info["providentFund"]["employeeAmount"], "color": "#d96561"},
            {"label": "PT", "value": latest_employee_payroll.professional_tax if latest_employee_payroll else salary_info["tax"]["professionalTax"], "color": "#a7a39d"},
            {"label": "Other", "value": latest_employee_payroll.other_deductions if latest_employee_payroll else salary_info["tax"]["otherDeduction"], "color": "#8b72c9"},
        ]
        salary_breakdown = [{**item, "display": _compact_currency_text(item["value"])} for item in salary_breakdown]
    net_salary_trend = [
        {
            "label": window["label"],
            "value": next(
                (
                    round(payroll.net_salary, 2)
                    for payroll in payrolls_by_user.get(current_user.id, [])
                    if payroll.year == window["year"] and payroll.month == window["month"]
                ),
                0.0,
            ),
        }
        for window in month_series
    ]
    employee_leave_days = approved_leave_days_by_user.get(current_user.id, 0)
    present_days = attendance["summary"]["presentDays"]
    absent_days = attendance["summary"]["absentDays"]
    total_balance_days = round(sum(balance.balance for balance in employee_balances), 1)
    current_net_salary = latest_employee_payroll.net_salary if latest_employee_payroll else 0.0
    attendance_rate = round(_safe_ratio(present_days, business_days_current) * 100, 1)
    return {
        "variant": "employee",
        "cards": [
            {"label": "Present days", "value": str(present_days), "note": f"of {business_days_current} working days", "tone": "success"},
            {"label": "Leave balance", "value": str(int(round(total_balance_days))), "note": "days remaining", "tone": "accent"},
            {"label": "Net salary", "value": _compact_currency_text(current_net_salary), "note": f"latest payroll · {latest_employee_payroll.month:02d}/{latest_employee_payroll.year}" if latest_employee_payroll else "Awaiting payroll run", "tone": "success"},
            {"label": "Attendance rate", "value": _percent_text(attendance_rate), "note": f"{employee_leave_days} leave day(s) used", "tone": "warning"},
        ],
        "attendanceThisMonth": [
            {"label": "Present", "value": present_days, "display": str(present_days), "color": "#58a47b"},
            {"label": "Leave", "value": employee_leave_days, "display": str(employee_leave_days), "color": "#e3a641"},
            {"label": "Absent", "value": absent_days, "display": str(absent_days), "color": "#d96561"},
        ],
        "leaveBalanceByType": employee_balance_items,
        "salaryBreakdown": salary_breakdown,
        "netSalaryTrend": net_salary_trend,
    }


@router.get("/attendance")
async def attendance(
    request: Request,
    employeeId: int | None = Query(None),
    month: str | None = Query(None),
    day: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
):
    current_user = await _get_session_user(request, session)
    target_user = current_user
    if employeeId and employeeId != current_user.id:
        if current_user.role not in DIRECTORY_ROLES:
            raise HTTPException(status_code=403, detail="You cannot view another employee's attendance.")
        target_user = await session.get(User, employeeId)
        if target_user is None:
            raise HTTPException(status_code=404, detail="Employee not found.")
    return await _attendance_payload(session, target_user, month, day)


@router.post("/attendance/mark")
async def mark_attendance(
    payload: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_csrf_token: str | None = Header(default=None),
):
    _require_csrf(request, x_csrf_token)
    current_user = await _get_session_user(request, session)
    if current_user.role == "Admin":
        raise HTTPException(status_code=403, detail="Admins cannot mark their own attendance.")
    action = str(payload.get("action", "")).lower()
    use_server_time = bool(payload.get("useServerTime")) or not payload.get("date") or not payload.get("time")
    timestamp = datetime.now().astimezone() if use_server_time else _parse_datetime(str(payload.get("date")), str(payload.get("time")))
    attendance_date = timestamp.date() if use_server_time else date.fromisoformat(str(payload.get("date")))
    record = (
        await session.execute(
            select(Attendance).where(Attendance.user_id == current_user.id, Attendance.date == attendance_date)
        )
    ).scalar_one_or_none()

    if action == "checkin":
        if record is None:
            record = Attendance(user_id=current_user.id, date=attendance_date)
            session.add(record)
        active_session_started = record.session_started_at or (record.check_in and not record.check_out)
        if active_session_started:
            raise HTTPException(status_code=400, detail="Attendance is already checked in for this date.")
        if not record.check_in:
            record.check_in = timestamp
        record.session_started_at = timestamp
        record.pause_started_at = None
        record.paused_minutes = 0.0
        record.check_out = None
        record.accumulated_hours = round(record.working_hours or record.accumulated_hours or 0.0, 2)
        record.working_hours = round(record.accumulated_hours or 0.0, 2)
        record.extra_hours = max(round((record.working_hours or 0) - 8, 2), 0)
        record.status = "Late" if timestamp.time() > time(9, 5) else "Working"
    elif action == "pause":
        if record is None or not (record.session_started_at or (record.check_in and not record.check_out)):
            raise HTTPException(status_code=400, detail="Please check in before pausing your timer.")
        if record.pause_started_at:
            raise HTTPException(status_code=400, detail="Your attendance timer is already paused.")
        record.pause_started_at = timestamp
        record.status = "Paused"
    elif action == "resume":
        if record is None or not (record.session_started_at or (record.check_in and not record.check_out)):
            raise HTTPException(status_code=400, detail="Please check in before resuming your timer.")
        if not record.pause_started_at:
            raise HTTPException(status_code=400, detail="Your attendance timer is not paused.")
        paused_duration = max((timestamp - record.pause_started_at).total_seconds() / 60, 0)
        record.paused_minutes = round((record.paused_minutes or 0) + paused_duration, 2)
        record.pause_started_at = None
        record.status = "Working"
    elif action == "checkout":
        if record is None or not (record.session_started_at or record.check_in):
            raise HTTPException(status_code=400, detail="Please check in before checking out.")
        if not record.session_started_at:
            record.session_started_at = record.check_in
        if record.pause_started_at:
            paused_duration = max((timestamp - record.pause_started_at).total_seconds() / 60, 0)
            record.paused_minutes = round((record.paused_minutes or 0) + paused_duration, 2)
            record.pause_started_at = None
        record.check_out = timestamp
        session_seconds = max(
            (timestamp - record.session_started_at).total_seconds() - float(record.paused_minutes or 0) * 60,
            0,
        )
        total_hours = round(float(record.accumulated_hours or 0) + session_seconds / 3600, 2)
        record.working_hours = total_hours
        record.accumulated_hours = total_hours
        record.session_started_at = None
        record.paused_minutes = 0.0
        record.extra_hours = max(round((record.working_hours or 0) - 8, 2), 0)
        record.status = "Checked Out"
    else:
        raise HTTPException(status_code=400, detail="Unsupported attendance action.")

    await session.commit()
    await _log_action(session, current_user.id, f"Marked attendance {action}", "attendance", attendance_date.isoformat())
    return {"ok": True}


@router.get("/leave-types")
async def leave_types(request: Request, session: AsyncSession = Depends(get_db)):
    await _get_session_user(request, session)
    leave_types_result = await session.execute(select(LeaveType).order_by(LeaveType.name.asc()))
    return {
        "leaveTypes": [
            {"id": leave_type.id, "name": leave_type.name, "defaultBalance": leave_type.default_balance}
            for leave_type in leave_types_result.scalars().all()
        ]
    }


@router.post("/leave-types")
async def create_leave_type(
    payload: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_csrf_token: str | None = Header(default=None),
):
    _require_csrf(request, x_csrf_token)
    current_user = await _get_session_user(request, session)
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Only admins can create leave types.")
    name = str(payload.get("name", "")).strip()
    default_balance = _safe_float(payload.get("defaultBalance"), 0.0)
    if not name:
        raise HTTPException(status_code=400, detail="Leave type name is required.")
    existing = (
        await session.execute(select(LeaveType).where(LeaveType.name == name))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=400, detail="A leave type with this name already exists.")
    leave_type = LeaveType(name=name, default_balance=default_balance)
    session.add(leave_type)
    await session.flush()
    users = (await session.execute(select(User).where(User.is_active == True))).scalars().all()
    for user in users:
        session.add(
            LeaveBalance(user_id=user.id, leave_type_id=leave_type.id, balance=default_balance)
        )
    await session.commit()
    await _log_action(session, current_user.id, "Created leave type", "leave_type", str(leave_type.id))
    return {"ok": True}


@router.get("/leave-balances")
async def leave_balances(
    request: Request,
    employeeId: int | None = Query(None),
    session: AsyncSession = Depends(get_db),
):
    current_user = await _get_session_user(request, session)
    target_user_id = employeeId or current_user.id
    if target_user_id != current_user.id and current_user.role not in DIRECTORY_ROLES:
        raise HTTPException(status_code=403, detail="You cannot view another employee's leave balance.")
    balances = (
        await session.execute(select(LeaveBalance).where(LeaveBalance.user_id == target_user_id))
    ).scalars().all()
    leave_type_map = {leave_type.id: leave_type for leave_type in (await session.execute(select(LeaveType))).scalars().all()}
    return {
        "balances": [
            {
                "id": balance.id,
                "employeeId": balance.user_id,
                "leaveTypeId": balance.leave_type_id,
                "leaveTypeName": leave_type_map[balance.leave_type_id].name,
                "balance": round(balance.balance, 2),
            }
            for balance in balances
        ]
    }


@router.get("/leaves")
async def list_leaves(
    request: Request,
    month: str | None = Query(None),
    status: str | None = Query(None),
    fromDate: str | None = Query(None),
    toDate: str | None = Query(None),
    employeeId: int | None = Query(None),
    session: AsyncSession = Depends(get_db),
):
    current_user = await _get_session_user(request, session)
    stmt = select(LeaveRequest).order_by(LeaveRequest.created_at.desc())
    if current_user.role == "Employee":
        stmt = stmt.where(LeaveRequest.user_id == current_user.id)
    elif employeeId:
        stmt = stmt.where(LeaveRequest.user_id == employeeId)
    if status:
        stmt = stmt.where(LeaveRequest.status == status)
    if month:
        start_date, end_date = _month_bounds(month)
        stmt = stmt.where(LeaveRequest.end_date >= start_date, LeaveRequest.start_date <= end_date)
    if fromDate:
        stmt = stmt.where(LeaveRequest.end_date >= date.fromisoformat(fromDate))
    if toDate:
        stmt = stmt.where(LeaveRequest.start_date <= date.fromisoformat(toDate))
    leaves = (await session.execute(stmt)).scalars().all()
    return {"leaveRequests": await _serialize_leaves(session, leaves)}


@router.post("/leaves")
async def create_leave(
    payload: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_csrf_token: str | None = Header(default=None),
):
    _require_csrf(request, x_csrf_token)
    current_user = await _get_session_user(request, session)
    employee_id = int(payload.get("employeeId") or current_user.id)
    if current_user.role == "Employee":
        employee_id = current_user.id
    elif current_user.role not in REVIEW_LEAVE_ROLES and current_user.role != "Payroll Officer" and employee_id != current_user.id:
        raise HTTPException(status_code=403, detail="You cannot create leave for another employee.")
    leave_type = await session.get(LeaveType, int(payload.get("leaveTypeId")))
    if leave_type is None:
        raise HTTPException(status_code=400, detail="Please select a valid leave type.")
    start_date = date.fromisoformat(str(payload.get("startDate")))
    end_date = date.fromisoformat(str(payload.get("endDate")))
    if end_date < start_date:
        raise HTTPException(status_code=400, detail="End date cannot be earlier than the start date.")
    leave = LeaveRequest(
        user_id=employee_id,
        leave_type=leave_type.name,
        start_date=start_date,
        end_date=end_date,
        days_requested=(end_date - start_date).days + 1,
        reason=str(payload.get("reason", "")).strip(),
        status="Pending",
    )
    session.add(leave)
    await session.commit()
    await _log_action(session, current_user.id, "Submitted leave request", "leave", str(leave.id))
    return {"ok": True}


@router.patch("/leaves/{leave_id}")
async def update_leave_status(
    leave_id: int,
    payload: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_csrf_token: str | None = Header(default=None),
):
    _require_csrf(request, x_csrf_token)
    current_user = await _get_session_user(request, session)
    leave = await session.get(LeaveRequest, leave_id)
    if leave is None:
        raise HTTPException(status_code=404, detail="Leave request not found.")
    if current_user.role not in REVIEW_LEAVE_ROLES:
        raise HTTPException(status_code=403, detail="Only Admin and HR Officer can review leaves.")

    action = str(payload.get("action", "")).lower()
    leave_type = (
        await session.execute(select(LeaveType).where(LeaveType.name == leave.leave_type))
    ).scalar_one_or_none()
    balance = None
    if leave_type is not None:
        balance = (
            await session.execute(
                select(LeaveBalance).where(
                    LeaveBalance.user_id == leave.user_id,
                    LeaveBalance.leave_type_id == leave_type.id,
                )
            )
        ).scalar_one_or_none()

    if action == "approve":
        if balance and balance.balance < leave.days_requested:
            raise HTTPException(status_code=400, detail="This employee does not have enough leave balance.")
        if leave.status != "Approved" and balance:
            balance.balance -= leave.days_requested
        leave.status = "Approved"
        leave.approved_by = current_user.id
    elif action == "reject":
        leave.status = "Rejected"
        leave.approved_by = current_user.id
    elif action == "cancel":
        if leave.status == "Approved" and balance:
            balance.balance += leave.days_requested
        leave.status = "Cancelled"
        leave.approved_by = current_user.id
    else:
        raise HTTPException(status_code=400, detail="Unsupported leave action.")

    await session.commit()
    await _log_action(session, current_user.id, f"{action.title()}d leave request", "leave", str(leave.id))
    return {"ok": True}


@router.get("/payroll/structures")
async def get_salary_structures(
    request: Request,
    employeeId: int | None = Query(None),
    session: AsyncSession = Depends(get_db),
):
    current_user = await _get_session_user(request, session)
    stmt = select(SalaryStructure).order_by(SalaryStructure.user_id.asc())
    if current_user.role == "Employee":
        stmt = stmt.where(SalaryStructure.user_id == current_user.id)
    elif employeeId:
        stmt = stmt.where(SalaryStructure.user_id == employeeId)
    structures = (await session.execute(stmt)).scalars().all()
    users = {user.id: user for user in (await session.execute(select(User))).scalars().all()}
    return {
        "structures": [
            {
                "id": structure.id,
                "employeeId": structure.user_id,
                "employeeName": _full_name(users[structure.user_id]),
                "monthWage": round(structure.month_wage, 2),
                "workingDaysPerWeek": structure.working_days_per_week,
                "breakHours": structure.break_hours,
                "basicPercentage": structure.basic_percentage,
                "hraPercentage": structure.hra_percentage,
                "standardAllowancePercentage": structure.standard_allowance_percentage,
                "performanceBonusPercentage": structure.performance_bonus_percentage,
                "leaveTravelAllowancePercentage": structure.leave_travel_allowance_percentage,
                "fixedAllowancePercentage": structure.fixed_allowance_percentage,
                "employeePfPercentage": structure.employee_pf_percentage,
                "employerPfPercentage": structure.employer_pf_percentage,
                "professionalTax": structure.professional_tax,
                "otherDeduction": structure.other_deduction,
                "salaryInfo": _salary_info(structure),
            }
            for structure in structures
        ]
    }


@router.post("/payroll/structures")
async def save_salary_structure(
    payload: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_csrf_token: str | None = Header(default=None),
):
    _require_csrf(request, x_csrf_token)
    current_user = await _get_session_user(request, session)
    if current_user.role not in PAYROLL_ROLES:
        raise HTTPException(status_code=403, detail="Only Admin and Payroll Officer can manage salary structures.")
    employee_id = int(payload.get("employeeId"))
    structure = await _get_or_create_salary_structure(session, employee_id)
    structure.month_wage = _safe_float(payload.get("monthWage"), structure.month_wage)
    structure.working_days_per_week = int(payload.get("workingDaysPerWeek") or structure.working_days_per_week)
    structure.break_hours = _safe_float(payload.get("breakHours"), structure.break_hours)
    structure.basic_percentage = _safe_float(payload.get("basicPercentage"), structure.basic_percentage)
    structure.hra_percentage = _safe_float(payload.get("hraPercentage"), structure.hra_percentage)
    structure.standard_allowance_percentage = _safe_float(payload.get("standardAllowancePercentage"), structure.standard_allowance_percentage)
    structure.performance_bonus_percentage = _safe_float(payload.get("performanceBonusPercentage"), structure.performance_bonus_percentage)
    structure.leave_travel_allowance_percentage = _safe_float(payload.get("leaveTravelAllowancePercentage"), structure.leave_travel_allowance_percentage)
    structure.fixed_allowance_percentage = _safe_float(payload.get("fixedAllowancePercentage"), structure.fixed_allowance_percentage)
    structure.employee_pf_percentage = _safe_float(payload.get("employeePfPercentage"), structure.employee_pf_percentage)
    structure.employer_pf_percentage = _safe_float(payload.get("employerPfPercentage"), structure.employer_pf_percentage)
    structure.professional_tax = _safe_float(payload.get("professionalTax"), structure.professional_tax)
    structure.other_deduction = _safe_float(payload.get("otherDeduction"), structure.other_deduction)
    await session.commit()
    await _log_action(session, current_user.id, "Saved salary structure", "payroll", str(employee_id))
    return {"ok": True}


async def _ensure_payroll_for_month(session: AsyncSession, month_value: str, generated_by: User) -> dict[str, Any]:
    year, month_number = [int(part) for part in month_value.split("-", 1)]
    users = (
        await session.execute(
            select(User).where(User.is_active == True, User.role != "Admin").order_by(User.first_name.asc(), User.last_name.asc())
        )
    ).scalars().all()
    for user in users:
        structure = await _get_or_create_salary_structure(session, user.id)
        attendance_payload = await _attendance_payload(session, user, month_value, None)
        summary = attendance_payload["summary"]
        salary_info = _salary_info(structure)
        basic_salary = salary_info["breakdown"]["basicSalary"]["amount"]
        overtime_pay = round(summary["extraHours"] * (structure.month_wage / 240), 2)
        gross_salary = round(structure.month_wage + overtime_pay, 2)
        pf_contribution = salary_info["providentFund"]["employeeAmount"]
        other_deduction = round(structure.other_deduction, 2)
        professional_tax = round(structure.professional_tax, 2)
        net_salary = round(gross_salary - pf_contribution - professional_tax - other_deduction, 2)
        existing = (
            await session.execute(
                select(Payroll).where(Payroll.user_id == user.id, Payroll.month == month_number, Payroll.year == year)
            )
        ).scalar_one_or_none()
        if existing is None:
            existing = Payroll(user_id=user.id, month=month_number, year=year, generated_by=generated_by.id)
            session.add(existing)
        existing.working_days = summary["payableDays"]
        existing.total_hours = summary["workedHours"]
        existing.extra_hours = summary["extraHours"]
        existing.approved_leaves = max(summary["payableDays"] - summary["presentDays"], 0)
        existing.basic_salary = basic_salary
        existing.bonus = salary_info["breakdown"]["performanceBonus"]["amount"]
        existing.overtime_pay = overtime_pay
        existing.pf_contribution = pf_contribution
        existing.professional_tax = professional_tax
        existing.other_deductions = other_deduction
        existing.gross_salary = gross_salary
        existing.net_salary = net_salary
        existing.generated_by = generated_by.id
        await session.flush()
        payslip = (
            await session.execute(select(Payslip).where(Payslip.payroll_id == existing.id))
        ).scalar_one_or_none()
        if payslip is None:
            session.add(Payslip(payroll_id=existing.id, user_id=user.id, pdf_path=f"{user.employee_code}-{month_value}.pdf"))
    await session.commit()
    payruns = await _payrun_payloads(session, month=month_value)
    return payruns[0] if payruns else {"month": month_value, "status": "Locked", "records": []}


@router.post("/payruns/generate")
async def generate_payrun(
    payload: dict[str, Any],
    request: Request,
    session: AsyncSession = Depends(get_db),
    x_csrf_token: str | None = Header(default=None),
):
    _require_csrf(request, x_csrf_token)
    current_user = await _get_session_user(request, session)
    if current_user.role not in PAYROLL_ROLES:
        raise HTTPException(status_code=403, detail="Only Admin and Payroll Officer can generate payruns.")
    month_value = str(payload.get("month") or date.today().strftime("%Y-%m"))
    payrun = await _ensure_payroll_for_month(session, month_value, current_user)
    await _log_action(session, current_user.id, "Generated payrun", "payrun", month_value)
    return payrun


@router.get("/payruns")
async def list_payruns(
    request: Request,
    month: str | None = Query(None),
    status: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
):
    current_user = await _get_session_user(request, session)
    if current_user.role not in PAYROLL_ROLES:
        raise HTTPException(status_code=403, detail="Only Admin and Payroll Officer can view payruns.")
    return {"payruns": await _payrun_payloads(session, month=month, status=status)}


@router.get("/payslips")
async def list_payslips(
    request: Request,
    employeeId: int | None = Query(None),
    month: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
):
    current_user = await _get_session_user(request, session)
    stmt = select(Payslip).options(joinedload(Payslip.payroll)).order_by(Payslip.generated_at.desc())
    if current_user.role == "Employee":
        stmt = stmt.where(Payslip.user_id == current_user.id)
    elif employeeId:
        stmt = stmt.where(Payslip.user_id == employeeId)
    payslips = (await session.execute(stmt)).scalars().all()
    if month:
        year, month_number = [int(part) for part in month.split("-", 1)]
        payslips = [payslip for payslip in payslips if payslip.payroll and payslip.payroll.year == year and payslip.payroll.month == month_number]
    serialized = []
    for payslip in payslips:
        payroll = payslip.payroll
        if payroll is None:
            continue
        serialized.append(
            {
                "id": payslip.id,
                "employeeId": payslip.user_id,
                "month": f"{payroll.year}-{payroll.month:02d}",
                "earnings": {
                    "grossPay": round(payroll.gross_salary, 2),
                    "basicSalary": round(payroll.basic_salary, 2),
                    "bonus": round(payroll.bonus, 2),
                    "overtimePay": round(payroll.overtime_pay, 2),
                },
                "deductions": {
                    "providentFund": round(payroll.pf_contribution, 2),
                    "professionalTax": round(payroll.professional_tax, 2),
                    "otherDeductions": round(payroll.other_deductions, 2),
                    "totalDeductions": round(payroll.pf_contribution + payroll.professional_tax + payroll.other_deductions, 2),
                },
                "netPay": round(payroll.net_salary, 2),
                "status": "Finalized",
            }
        )
    return {"payslips": serialized}


@router.get("/payslips/download")
async def download_payslip(
    request: Request,
    employeeId: int = Query(...),
    month: str = Query(...),
    session: AsyncSession = Depends(get_db),
):
    current_user = await _get_session_user(request, session)
    if current_user.role == "Employee" and current_user.id != employeeId:
        raise HTTPException(status_code=403, detail="You cannot download another employee's payslip.")
    employee = await session.get(User, employeeId)
    if employee is None:
        raise HTTPException(status_code=404, detail="Employee not found.")
    year, month_number = [int(part) for part in month.split("-", 1)]
    payroll = (
        await session.execute(
            select(Payroll)
            .where(Payroll.user_id == employeeId, Payroll.year == year, Payroll.month == month_number)
            .order_by(Payroll.generated_at.desc())
        )
    ).scalars().first()
    if payroll is None:
        raise HTTPException(status_code=404, detail="Payslip not found.")

    company = await _get_company(session)
    structure = (
        await session.execute(select(SalaryStructure).where(SalaryStructure.user_id == employeeId))
    ).scalar_one_or_none()
    salary_info = _salary_info(structure) if structure else None
    breakdown = salary_info["breakdown"] if salary_info else {}

    earnings_rows: list[tuple[str, float, float]] = []
    ordered_earnings = [
        ("Basic salary", breakdown.get("basicSalary", {}).get("amount", payroll.basic_salary)),
        ("House Rent Allowance (HRA)", breakdown.get("houseRentAllowance", {}).get("amount", 0.0)),
        ("Special allowance", breakdown.get("standardAllowance", {}).get("amount", 0.0)),
        ("Performance bonus", breakdown.get("performanceBonus", {}).get("amount", 0.0)),
        ("Travel allowance", breakdown.get("leaveTravelAllowance", {}).get("amount", 0.0)),
        ("Fixed allowance", breakdown.get("fixedAllowance", {}).get("amount", 0.0)),
    ]
    for label, amount in ordered_earnings:
        if amount and amount > 0:
            earnings_rows.append((label, round(amount, 2), round(amount * 12, 2)))
    if payroll.bonus > 0:
        earnings_rows.append(("Bonus", round(payroll.bonus, 2), round(payroll.bonus * 12, 2)))
    if payroll.overtime_pay > 0:
        earnings_rows.append(("Overtime pay", round(payroll.overtime_pay, 2), round(payroll.overtime_pay * 12, 2)))
    if not earnings_rows:
        earnings_rows.append(("Gross salary", round(payroll.gross_salary, 2), round(payroll.gross_salary * 12, 2)))

    deduction_rows = [
        ("Provident Fund (PF)", round(payroll.pf_contribution, 2), round(payroll.pf_contribution * 12, 2)),
        ("Professional Tax (PT)", round(payroll.professional_tax, 2), round(payroll.professional_tax * 12, 2)),
    ]
    if payroll.other_deductions > 0:
        deduction_rows.append(
            ("Other deductions", round(payroll.other_deductions, 2), round(payroll.other_deductions * 12, 2))
        )
    if not any(label.startswith("Other") for label, *_ in deduction_rows):
        deduction_rows.append(("Other deductions", 0.0, 0.0))

    statement_month = _month_label(month)
    payslip_code = f"PS-{year}-{month_number:02d}-{employee.employee_code.split('-')[-1]}"
    working_days_total = _business_days(date(year, month_number, 1), date(year, month_number, monthrange(year, month_number)[1]))

    pdf_bytes = _build_payslip_pdf_themed(
        company_name=company.company_name,
        company_code=payslip_code,
        employee_name=_full_name(employee),
        employee_id=employee.employee_code,
        department=employee.department,
        designation=employee.designation or employee.role,
        date_of_joining=employee.date_of_joining.strftime("%d %B %Y") if employee.date_of_joining else "-",
        salary_effective_from=statement_month,
        working_days=f"{payroll.working_days} of {working_days_total}",
        leave_taken=f"{payroll.approved_leaves} day(s)",
        statement_month=statement_month,
        earnings_rows=earnings_rows,
        deduction_rows=deduction_rows,
        net_salary_monthly=round(payroll.net_salary, 2),
        net_salary_yearly=round(payroll.net_salary * 12, 2),
        generated_on=datetime.now().strftime("%d %B %Y"),
    )
    filename = f"hurema-payslip-{employee.employee_code}-{month}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/reports")
async def reports(
    request: Request,
    type: str = Query(...),
    month: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
):
    current_user = await _get_session_user(request, session)
    if current_user.role not in DIRECTORY_ROLES:
        raise HTTPException(status_code=403, detail="You do not have access to reports.")
    if type == "attendance":
        users = (await session.execute(select(User).where(User.role != "Admin"))).scalars().all()
        rows = []
        for user in users:
            payload = await _attendance_payload(session, user, month, None)
            rows.append(
                {
                    "employeeId": user.employee_code,
                    "employeeName": _full_name(user),
                    "department": user.department,
                    "presentDays": payload["summary"]["presentDays"],
                    "absentDays": payload["summary"]["absentDays"],
                    "payableDays": payload["summary"]["payableDays"],
                    "extraHours": payload["summary"]["extraHours"],
                }
            )
        return {"rows": rows}
    if type == "leave":
        leaves = (await list_leaves(request, month=month, session=session))["leaveRequests"]
        return {"rows": leaves}
    if type == "payroll":
        if current_user.role not in PAYROLL_ROLES:
            raise HTTPException(status_code=403, detail="You do not have access to payroll reports.")
        return {"rows": (await list_payslips(request, month=month, session=session))["payslips"]}
    if type == "employees":
        employees = (await list_employees(request, includeAdmins=True, session=session))["employees"]
        return {
            "rows": [
                {
                    "employeeId": employee["employeeId"],
                    "fullName": employee["fullName"],
                    "email": employee["email"],
                    "role": employee["role"],
                    "department": employee["department"],
                    "designation": employee["designation"],
                    "active": employee["active"],
                }
                for employee in employees
            ]
        }
    raise HTTPException(status_code=400, detail="Unsupported report type.")


@router.get("/reports/attendance-pdf")
async def attendance_report_pdf(
    request: Request,
    month: str | None = Query(None),
    session: AsyncSession = Depends(get_db),
):
    current_user = await _get_session_user(request, session)
    if current_user.role not in DIRECTORY_ROLES:
        raise HTTPException(status_code=403, detail="You do not have access to reports.")
    company = await _get_company(session)
    report_rows = (await reports(request=request, type="attendance", month=month, session=session))["rows"]
    report_month = _month_label(month or date.today().strftime("%Y-%m"))
    pdf_bytes = _build_attendance_report_pdf(
        company_name=company.company_name,
        report_month=report_month,
        rows=report_rows,
    )
    filename = f"hurema-attendance-report-{(month or date.today().strftime('%Y-%m'))}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/audit-logs")
async def audit_logs(request: Request, session: AsyncSession = Depends(get_db)):
    current_user = await _get_session_user(request, session)
    if current_user.role != "Admin":
        raise HTTPException(status_code=403, detail="Only admins can view audit logs.")
    users = {user.id: user for user in (await session.execute(select(User))).scalars().all()}
    logs = (
        await session.execute(select(AuditLog).order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).limit(100))
    ).scalars().all()
    return {
        "logs": [
            {
                "id": log.id,
                "createdAt": log.created_at.isoformat() if log.created_at else None,
                "action": log.action,
                "targetType": log.target_type,
                "targetId": log.target_id,
                "actorId": _full_name(users[log.actor_id]) if log.actor_id in users else "System",
            }
            for log in logs
        ]
    }
