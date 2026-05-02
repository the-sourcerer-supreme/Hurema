from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import get_settings
from app.core.database import db_manager
from app.api.routes import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle manager."""
    settings = get_settings()
    print(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    db_manager.initialize()
    await db_manager.create_tables()
    print("Database tables created successfully")

    yield

    await db_manager.close()
    print("Database connection closed")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title=settings.APP_NAME,
        description="EmPay HRMS + Payroll backend API",
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

    app.include_router(api_router)

    @app.get("/", tags=["root"])
    async def root():
        return {
            "message": "Welcome to EmPay HRMS Backend",
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

    return app


app = create_app()
