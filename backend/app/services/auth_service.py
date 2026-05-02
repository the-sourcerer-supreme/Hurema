from datetime import date, timedelta
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.email_service import EmailService
from app.core.employee_id_generator import generate_employee_code
from app.core.security import (
    create_access_token,
    generate_temporary_password,
    hash_password,
    verify_password,
    get_settings,
)
from app.crud.profile import EmployeeProfileCRUD
from app.crud.user import UserCRUD
from app.crud.email_log import EmailLogCRUD
from app.models.user import User
from app.schemas.profile import EmployeeProfileCreate
from app.schemas.user import UserCreate


class AuthService:
    @staticmethod
    async def create_employee(
        session: AsyncSession,
        user_create: UserCreate,
        creator_id: int,
    ) -> tuple[User, str]:
        if await UserCRUD.user_exists(session, user_create.email):
            raise ValueError("A user with that email already exists.")

        employee_code = await generate_employee_code(
            session,
            user_create.first_name,
            user_create.last_name,
            user_create.date_of_joining.year,
        )

        temporary_password = generate_temporary_password()
        try:
            user = await UserCRUD.create_user(
                session=session,
                user_data=user_create,
                employee_code=employee_code,
                temporary_password=temporary_password,
                creator_id=creator_id,
            )
        except IntegrityError as exc:
            await session.rollback()
            raise ValueError(
                "Unable to create user. The email or employee code may already exist."
            ) from exc

        profile_data = EmployeeProfileCreate(
            user_id=user.id,
            dob=user_create.date_of_birth,
            address=user_create.address,
            nationality=user_create.nationality,
            gender=user_create.gender,
            marital_status=user_create.marital_status,
            mobile=user_create.mobile,
            personal_email=user_create.personal_email,
            manager_id=user_create.manager_id,
            location=user_create.location,
            bank_name=user_create.bank_name,
            account_number=user_create.account_number,
            ifsc_code=user_create.ifsc_code,
            pan_number=user_create.pan_number,
            uan_number=user_create.uan_number,
            basic_salary=user_create.basic_salary,
        )
        await EmployeeProfileCRUD.create_profile(session, profile_data)

        await EmailService.send_credentials(
            email=user.email,
            employee_code=user.employee_code,
            temporary_password=temporary_password,
        )

        await EmailLogCRUD.create_log(
            session=session,
            user_id=user.id,
            email=user.email,
            credential_sent=True,
        )

        return user, temporary_password

    @staticmethod
    async def authenticate_user(session: AsyncSession, email: str, password: str) -> User | None:
        user = await UserCRUD.get_user_by_email(session, email)
        if not user or not user.is_active:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user

    @staticmethod
    def _landing_page_for_role(role: str) -> str:
        lookup = {
            "Admin": "/admin/dashboard",
            "HR": "/hr/dashboard",
            "Payroll Officer": "/payroll/dashboard",
            "Employee": "/employee/dashboard",
        }
        return lookup.get(role, "/")

    @staticmethod
    def create_token(user: User) -> dict:
        settings = get_settings()
        access_token = create_access_token(
            data={
                "sub": user.email,
                "user_id": user.id,
                "role": user.role,
            },
            expires_delta=timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
        )
        return {
            "access_token": access_token,
            "token_type": "bearer",
            "expires_in": settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            "first_login": user.is_first_login,
            "role": user.role,
            "landing_page": AuthService._landing_page_for_role(user.role),
        }

    @staticmethod
    async def change_password(
        session: AsyncSession,
        user: User,
        current_password: str,
        new_password: str,
    ) -> User:
        if not verify_password(current_password, user.hashed_password):
            raise ValueError("Current password is incorrect.")
        return await UserCRUD.set_password(session, user, new_password, is_first_login=False)

    @staticmethod
    async def forgot_password(session: AsyncSession, email: str) -> bool:
        user = await UserCRUD.get_user_by_email(session, email)
        if not user:
            return True
        temporary_password = generate_temporary_password()
        await UserCRUD.set_password(session, user, temporary_password, is_first_login=True)
        await EmailService.send_password_reset(email=user.email, temporary_password=temporary_password)
        await EmailLogCRUD.create_log(
            session=session,
            user_id=user.id,
            email=user.email,
            credential_sent=False,
        )
        return True
