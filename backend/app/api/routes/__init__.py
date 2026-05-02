from fastapi import APIRouter
from app.api.routes.auth import router as auth_router
from app.api.routes.users import router as users_router
from app.api.routes.profile import router as profile_router
from app.api.routes.attendance import router as attendance_router
from app.api.routes.leaves import router as leaves_router
from app.api.routes.payroll import router as payroll_router
from app.api.routes.payslips import router as payslips_router
from app.api.routes.dashboard import router as dashboard_router

api_router = APIRouter()
api_router.include_router(auth_router)
api_router.include_router(users_router)
api_router.include_router(profile_router)
api_router.include_router(attendance_router)
api_router.include_router(leaves_router)
api_router.include_router(payroll_router)
api_router.include_router(payslips_router)
api_router.include_router(dashboard_router)
