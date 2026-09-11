from pathlib import Path
import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.api.routes.documents import router as documents_router
from app.core.config import settings
from app.core.database import init_db
from app.core.logging import setup_logging


# ------------------------------------------------------------
# Paths
# ------------------------------------------------------------

# main.py:
# E:\Document Intelligence\backend\app\main.py
#
# parents[0] = ...\backend\app
# parents[1] = ...\backend
# parents[2] = ...\Document Intelligence
#
# Therefore parents[2] is the project root.

PROJECT_ROOT = Path(__file__).resolve().parents[2]

FRONTEND_DIR = PROJECT_ROOT / "frontend"
STATIC_DIR = FRONTEND_DIR / "static"
TEMPLATES_DIR = FRONTEND_DIR / "templates"


# ------------------------------------------------------------
# Logging
# ------------------------------------------------------------

setup_logging()

logger = logging.getLogger(__name__)


# ------------------------------------------------------------
# FastAPI Application
# ------------------------------------------------------------

app = FastAPI(
    title=settings.app_name,
    description=(
        "Intelligent Document Extraction, Validation "
        "& API Platform"
    ),
    version="1.0.0",
)


# ------------------------------------------------------------
# Startup
# ------------------------------------------------------------

@app.on_event("startup")
def startup_event():

    logger.info("Starting Document Intelligence API")

    try:
        init_db()

        logger.info(
            "Database initialization successful"
        )

    except Exception:

        logger.exception(
            "Database initialization failed"
        )

        raise


# ------------------------------------------------------------
# API Routes
# ------------------------------------------------------------

app.include_router(documents_router)


# ------------------------------------------------------------
# Static Files
# ------------------------------------------------------------

if STATIC_DIR.exists():

    app.mount(
        "/static",
        StaticFiles(directory=str(STATIC_DIR)),
        name="static",
    )

else:

    logger.warning(
        "Frontend static directory not found: %s",
        STATIC_DIR,
    )


# ------------------------------------------------------------
# Frontend Dashboard
# ------------------------------------------------------------

@app.get("/", include_in_schema=False)
def dashboard():

    dashboard_file = TEMPLATES_DIR / "dashboard.html"

    if not dashboard_file.exists():

        logger.error(
            "Dashboard file not found: %s",
            dashboard_file,
        )

        raise FileNotFoundError(
            f"Dashboard file not found: {dashboard_file}"
        )

    return FileResponse(
        dashboard_file
    )


# ------------------------------------------------------------
# Health Check
# ------------------------------------------------------------

@app.get(
    "/api/v1/health",
    tags=["Health"],
)
def health_check():

    return {
        "status": "healthy",
        "service": settings.app_name,
        "version": "1.0.0",
    }