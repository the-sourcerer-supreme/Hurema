import asyncio
import json
import logging
from typing import List
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from pydantic import EmailStr

from app.core.config import get_settings

logger = logging.getLogger(__name__)

def _send_brevo_request(payload: dict) -> None:
    settings = get_settings()
    request = Request(
        settings.BREVO_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "accept": "application/json",
            "api-key": settings.BREVO_API_KEY,
            "content-type": "application/json",
        },
        method="POST",
    )
    with urlopen(request, timeout=20) as response:
        response.read()


class EmailService:
    @staticmethod
    async def send_email(subject: str, recipients: List[EmailStr], body: str) -> bool:
        settings = get_settings()
        if not settings.EMAILS_ENABLED or not settings.BREVO_API_KEY or not recipients:
            return False

        try:
            payload = {
                "sender": {
                    "name": settings.BREVO_SENDER_NAME or settings.MAIL_FROM_NAME,
                    "email": settings.BREVO_SENDER_EMAIL or settings.MAIL_FROM,
                },
                "to": [{"email": str(email)} for email in recipients],
                "subject": subject,
                "htmlContent": body,
            }
            await asyncio.to_thread(_send_brevo_request, payload)
            return True
        except (HTTPError, URLError, TimeoutError, ValueError) as error:
            logger.warning("Failed to send Brevo email: %s", error)
            return False

    @staticmethod
    async def send_credentials(
        email: EmailStr,
        employee_code: str,
        temporary_password: str,
        company_name: str,
    ) -> bool:
        body = (
            "<div style=\"font-family:Segoe UI,Arial,sans-serif;max-width:640px;margin:0 auto;"
            "background:#ffffff;border:1px solid #e1e3eb;border-radius:20px;overflow:hidden;\">"
            "<div style=\"padding:24px 28px;background:#735a7e;color:#ffffff;\">"
            "<div style=\"font-size:24px;font-weight:700;\">Hurema</div>"
            "<div style=\"font-size:13px;opacity:0.9;margin-top:6px;\">Your workspace access is ready</div>"
            "</div>"
            "<div style=\"padding:28px;\">"
            f"<p style=\"margin:0 0 16px;color:#21273a;\">Welcome to <strong>{company_name}</strong>.</p>"
            "<p style=\"margin:0 0 18px;color:#576178;line-height:1.6;\">"
            "An administrator has created your Hurema account. Use the credentials below to sign in."
            "</p>"
            "<table style=\"width:100%;border-collapse:collapse;margin:0 0 20px;\">"
            f"<tr><td style=\"padding:10px 0;color:#6a7387;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;\">Employee ID</td><td style=\"padding:10px 0;color:#21273a;font-weight:700;\">{employee_code}</td></tr>"
            f"<tr><td style=\"padding:10px 0;color:#6a7387;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;\">Email</td><td style=\"padding:10px 0;color:#21273a;font-weight:700;\">{email}</td></tr>"
            f"<tr><td style=\"padding:10px 0;color:#6a7387;font-size:12px;text-transform:uppercase;letter-spacing:0.08em;\">Temporary Password</td><td style=\"padding:10px 0;color:#21273a;font-weight:700;\">{temporary_password}</td></tr>"
            "</table>"
            "<p style=\"margin:0;color:#576178;line-height:1.6;\">"
            "Please sign in and change your password after your first login."
            "</p>"
            "</div></div>"
        )
        return await EmailService.send_email(
            subject="Your Hurema Login Credentials",
            recipients=[email],
            body=body,
        )

    @staticmethod
    async def send_password_reset(email: EmailStr, temporary_password: str) -> bool:
        body = f"<p>Your password reset request has been processed.</p>"
        body += f"<p>Your temporary password is <strong>{temporary_password}</strong>.</p>"
        body += "<p>Please login and set a new secure password.</p>"
        return await EmailService.send_email(
            subject="Hurema HRMS Password Reset",
            recipients=[email],
            body=body,
        )
