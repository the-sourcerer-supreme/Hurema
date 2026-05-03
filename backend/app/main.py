from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import get_settings
from app.core.database import db_manager
from app.core.seed import ensure_seed_data
from app.api.routes import api_router
import app.models  # noqa: F401


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    settings = get_settings()
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    db_manager.initialize()
    await db_manager.create_tables()
    print("Database tables created successfully")
    async for session in db_manager.get_session():
        await ensure_seed_data(session)
        break

    yield

    await db_manager.close()
    print("Database connection closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"

    app = FastAPI(
        title=settings.APP_NAME,
        description="Hurema HRMS + Payroll backend API",
        version=settings.APP_VERSION,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def apply_security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "base-uri 'self'; "
            "form-action 'self'; "
            "frame-ancestors 'none'; "
            "object-src 'none'; "
            "script-src 'self'; "
            "connect-src 'self'; "
            "img-src 'self' data: blob:; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:;"
        )
        return response

    app.include_router(api_router)

    @app.get("/", tags=["root"])
    async def root():
        if frontend_dist.exists():
            return FileResponse(frontend_dist / "index.html")
        return {
            "message": "Welcome to Hurema HRMS Backend",
            "version": settings.APP_VERSION,
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    @app.get("/health", tags=["root"])
    async def health_check():
        return {
            "status": "healthy",
            "service": settings.APP_NAME,
            "version": settings.APP_VERSION,
        }

    @app.get("/{full_path:path}", include_in_schema=False)
    async def frontend_fallback(full_path: str):
        if full_path.startswith(("api/", "auth/", "users/", "profile/", "attendance/", "leaves/", "payroll/", "payslips/", "dashboard/")):
            raise HTTPException(status_code=404, detail="Not found")
        if frontend_dist.exists():
            asset_path = frontend_dist / full_path
            if asset_path.exists() and asset_path.is_file():
                return FileResponse(asset_path)
            return FileResponse(frontend_dist / "index.html")
        raise HTTPException(status_code=404, detail="Frontend build not found.")

    return app


app = create_app()
