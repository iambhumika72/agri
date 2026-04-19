"""
api/main.py
============
Main FastAPI application entry point for the AgriSense Generative AI Platform.

Registers:
  - All API routers (health, forecast, alerts, recommendations, farmer_input)
  - CORS middleware for frontend integration
  - Lifespan handler for resource initialization (DB, models)
"""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Route imports
from .routes import health, forecast, alerts, recommendations
from .routes.farmer_input import router as farmer_input_router
from ingestion.farmer_input_ingestion import init_db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%SZ",
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lifespan — runs once on startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initializes database tables and application resources on startup."""
    log.info("AgriSense API starting up — version %s", app.version)
    log.info("Environment: %s", os.environ.get("AGRISENSE_ENV", "development"))
    
    try:
        await init_db()
        log.info("Database initialized successfully.")
    except Exception as e:
        log.error("Failed to initialize database: %s", str(e))
        
    yield
    log.info("AgriSense API shutting down gracefully.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    """Initializes and configures the FastAPI application."""
    app = FastAPI(
        title="AgriSense API",
        description=(
            "Generative AI platform for sustainable agriculture. "
            "Integrates Satellite (Sentinel-2/NDVI), IoT Sensors, "
            "Weather API, Historical DB, and Farmer Input channels."
        ),
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS Middleware ──────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ──────────────────────────────────────────────────────────
    app.include_router(health.router)
    app.include_router(forecast.router)
    app.include_router(alerts.router)
    app.include_router(recommendations.router)
    app.include_router(farmer_input_router)

    # ── Global exception handlers ─────────────────────────────────────────

    @app.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        log.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred."},
        )

    return app


app = create_app()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.main:app", host="0.0.0.0", port=8000, reload=True)
