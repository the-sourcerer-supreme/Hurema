from typing import List
import logging
from pydantic import EmailStr
from fastapi_mail import ConnectionConfig, FastMail, MessageSchema
from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _build_mail_config() -> ConnectionConfig:
    settings = get_settings()
    return ConnectionConfig(
        MAIL_USERNAME=settings.SMTP_USER,
        MAIL_PASSWORD=settings.SMTP_PASSWORD,
        MAIL_FROM=settings.MAIL_FROM,
        MAIL_FROM_NAME=settings.MAIL_FROM_NAME,
        MAIL_PORT=settings.SMTP_PORT,
        MAIL_SERVER=settings.SMTP_SERVER,
        MAIL_TLS=True,
        MAIL_SSL=False,
        USE_CREDENTIALS=True,
        VALIDATE_CERTS=True,
    )


class EmailService:
    @staticmethod
    async def send_email(subject: str, recipients: List[EmailStr], body: str) -> None:
        settings = get_settings()
        if not settings.EMAILS_ENABLED:
            return

        try:
            message = MessageSchema(
                subject=subject,
                recipients=recipients,
                body=body,
                subtype="html",
            )

            fm = FastMail(_build_mail_config())
            await fm.send_message(message)
        except Exception as e:
            logger.warning(f"Failed to send email: {str(e)}")

    @staticmethod
    async def send_credentials(email: EmailStr, employee_code: str, temporary_password: str) -> None:
        body = f"<p>Welcome to EmPay HRMS.</p>"
        body += f"<p>Your employee login credentials are:</p>"
        body += f"<ul><li><strong>Employee ID:</strong> {employee_code}</li>"
        body += f"<li><strong>Email:</strong> {email}</li>"
        body += f"<li><strong>Temporary Password:</strong> {temporary_password}</li></ul>"
        body += "<p>Please login and change your password immediately.</p>"
        await EmailService.send_email(
            subject="Your EmPay HRMS Login Credentials",
            recipients=[email],
            body=body,
        )

    @staticmethod
    async def send_password_reset(email: EmailStr, temporary_password: str) -> None:
        body = f"<p>Your password reset request has been processed.</p>"
        body += f"<p>Your temporary password is <strong>{temporary_password}</strong>.</p>"
        body += "<p>Please login and set a new secure password.</p>"
        await EmailService.send_email(
            subject="EmPay HRMS Password Reset",
            recipients=[email],
            body=body,
        )
