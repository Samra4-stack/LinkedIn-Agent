"""
app/main.py
────────────
FastAPI application entry point.

Features:
- Automatic Swagger UI at /docs
- ReDoc at /redoc
- CORS middleware
- Rate limiting
- Request logging
- Database initialization on startup
- Scheduler startup/shutdown lifecycle
- LinkedIn OAuth2 callback route
"""

from __future__ import annotations

import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.config import settings
from app.database.init_db import init_db
from app.services.scheduler_service import scheduler_service
from app.utils.logger import get_logger, setup_logging
from app.utils.rate_limiter import limiter

setup_logging()
log = get_logger(__name__)


# ─── Initialization ────────────────────────────────────────────

try:
    init_db()
    log.info("Database initialized successfully at startup.")
except Exception as e:
    log.error(f"Failed to initialize database at startup: {e}")

# ─── Lifespan ────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan manager.
    Runs startup tasks before yielding, shutdown tasks after.
    """
    log.info(f"Starting {settings.app_name} | env={settings.app_env}")

    # Scheduler is disabled for Serverless deployment. 
    # Vercel Cron will hit /api/v1/schedule/cron-trigger instead.
    # scheduler_service.start()

    yield  # Application runs here

    # Shutdown
    log.info("Shutting down...")
    # scheduler_service.stop()
    log.info(f"{settings.app_name} stopped")


# ─── FastAPI App ─────────────────────────────────────────────

app = FastAPI(
    title=settings.app_name,
    description="""
## 🤖 Autonomous LinkedIn AI Agent

An AI-powered agent that generates, reviews, and publishes LinkedIn posts.

### Workflow

1. **Generate** — `POST /api/v1/generate` — AI creates a post draft
2. **Preview** — `GET /api/v1/preview/{draft_id}` — Review the draft
3. **Edit** (optional) — `POST /api/v1/edit` — Modify any field
4. **Approve** — `POST /api/v1/preview/{draft_id}/approve` — Mark as approved
5. **Publish** — `POST /api/v1/publish` — Publish to LinkedIn

### ⚠️ Safety Guarantee
Posts are **NEVER** published automatically. Every post requires:
- Manual approval via the approve endpoint
- Explicit `confirm: true` in the publish request

### Authentication
Configure your LinkedIn credentials in `.env`. OAuth2 flow available via `/auth/linkedin`.
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "LinkedIn AI Agent",
        "url": "https://github.com/your-repo/linkedin-agent",
    },
    license_info={
        "name": "MIT License",
    },
)

# ─── Middleware ───────────────────────────────────────────────
# Serve static files for email preview
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Rate limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Request Logging Middleware ───────────────────────────────

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all incoming requests with timing."""
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000

    log.info(
        f"{request.method} {request.url.path} → {response.status_code} "
        f"[{duration_ms:.1f}ms]"
    )
    return response


# ─── Global Exception Handler ─────────────────────────────────

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Catch-all exception handler for unexpected errors."""
    log.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "error": "Internal server error",
            "detail": str(exc) if settings.debug else "An unexpected error occurred",
        },
    )


# ─── Routes ───────────────────────────────────────────────────

# Main API routes
app.include_router(api_router)


# ─── Health & Status ──────────────────────────────────────────

@app.get(
    "/health",
    tags=["System"],
    summary="Health check",
)
async def health_check():
    """API health check endpoint."""
    return {
        "status": "healthy",
        "app": settings.app_name,
        "version": "1.0.0",
        "environment": settings.app_env,
        "scheduler_running": scheduler_service.is_running,
    }


@app.get(
    "/",
    tags=["System"],
    summary="API root",
)
async def root():
    """API root — returns basic info and links."""
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
        "redoc": "/redoc",
        "health": "/health",
        "api": "/api/v1",
        "workflow": {
            "1_generate": "POST /api/v1/generate",
            "2_preview": "GET /api/v1/preview/{draft_id}",
            "3_approve": "POST /api/v1/preview/{draft_id}/approve",
            "4_publish": "POST /api/v1/publish",
        },
    }


# ─── LinkedIn OAuth2 Callback ─────────────────────────────────

@app.get(
    "/auth/linkedin/callback",
    tags=["Authentication"],
    summary="LinkedIn OAuth2 callback",
    description="OAuth2 callback URL. LinkedIn redirects here after user grants permission.",
)
async def linkedin_oauth_callback(code: str, state: str = ""):
    """
    Handle LinkedIn OAuth2 callback.
    Exchanges authorization code for access token.
    """
    from app.services.linkedin_service import LinkedInService, LinkedInServiceError

    if state != "linkedin_agent_auth":
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": "Invalid state parameter"},
        )

    linkedin = LinkedInService()
    try:
        token_data = await linkedin.exchange_code_for_token(code)
        access_token = token_data.get("access_token")
        expires_in = token_data.get("expires_in", 0)

        log.info(f"LinkedIn OAuth2 token obtained | expires_in={expires_in}s")

        return {
            "success": True,
            "message": "LinkedIn authentication successful!",
            "access_token": access_token,
            "expires_in_seconds": expires_in,
            "next_step": "Add this access_token to your .env as LINKEDIN_ACCESS_TOKEN",
        }
    except LinkedInServiceError as e:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"error": str(e)},
        )


@app.get(
    "/auth/linkedin",
    tags=["Authentication"],
    summary="Get LinkedIn OAuth2 authorization URL",
)
async def get_linkedin_auth_url():
    """Get the LinkedIn OAuth2 authorization URL to start the login flow."""
    from app.services.linkedin_service import LinkedInService
    linkedin = LinkedInService()
    auth_url = linkedin.get_auth_url()
    return {
        "auth_url": auth_url,
        "instructions": "Visit the auth_url in your browser to authorize the app",
    }
