"""
api/main.py
============
Main FastAPI application entry point for the Agri Generative AI Platform.

Registers:
  - All API routers (farmer_input, historical_db, health, etc.)
  - CORS middleware for the React frontend
  - Lifespan handler that initialises DB tables on startup
  - Global exception handlers

Run locally:
    uvicorn api.main:app --reload --host 0.0.0.0 --port 8000
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api.routes.farmer_input import router as farmer_input_router
from ingestion.farmer_input_ingestion import init_db

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lifespan — runs once on startup / shutdown
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialise database tables and any other startup resources."""
    logger.info("Agri platform starting up…")
    await init_db()
    logger.info("Database tables ready.")
    yield
    logger.info("Agri platform shutting down.")


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> FastAPI:
    application = FastAPI(
        title="Agri Generative AI Platform",
        description=(
            "Unified Data Pipeline for Sustainable Agriculture. "
            "Integrates Satellite (Sentinel-2/NDVI), IoT Sensors, "
            "Weather API, Historical DB, and Farmer Input channels."
        ),
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # ── CORS ──────────────────────────────────────────────────────────────
    # Allow the React dev server and any deployed frontend origin.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:3000",   # React dev server
            "http://localhost:5173",   # Vite dev server
            "https://agri.example.com",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Routers ───────────────────────────────────────────────────────────
    application.include_router(farmer_input_router)
    # Future routers (uncomment as modules are built):
    # application.include_router(satellite_router)
    # application.include_router(iot_router)
    # application.include_router(weather_router)
    # application.include_router(historical_db_router)
    # application.include_router(generative_router)

    # ── Global exception handlers ─────────────────────────────────────────

    @application.exception_handler(ValueError)
    async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content={"detail": str(exc)},
        )

    @application.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled exception on %s %s", request.method, request.url)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "An internal server error occurred."},
        )

    # ── Health probe ──────────────────────────────────────────────────────

    @application.get("/health", tags=["Health"], summary="Liveness probe")
    async def health_check():
        return {"status": "ok", "service": "agri-platform"}

    return application


app = create_app()
