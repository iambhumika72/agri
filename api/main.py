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
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Route imports
from .routes import health, forecast, alerts, recommendations, crop_profit
from .routes.farmer_input import router as farmer_input_router
from . import historical_db_routes
from ingestion.farmer_input_ingestion import init_db

# IoT Imports
from iot.router import router as iot_router
from iot.models import init_iot_db
from iot.cache import init_redis, close_redis
from iot.simulator import iot_simulator
from iot.hardware_bridge import hardware_bridge

# Chatbot Imports
import chatbot.models
from chatbot.router import router as chatbot_router

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
        
    try:
        await init_iot_db()
        log.info("IoT Database initialized successfully.")
    except Exception as e:
        log.error("Failed to initialize IoT database: %s", str(e))
        
    await init_redis()
    
    source = os.getenv("IOT_SOURCE", "simulator")
    if source == "simulator":
        await iot_simulator.start()
        log.info("IoT Simulator started — generating mock readings every 5min")
    elif source == "hardware":
        await hardware_bridge.start()
        log.info("IoT Hardware Bridge started")
        
    yield
    
    source = os.getenv("IOT_SOURCE", "simulator")
    if source == "simulator":
        await iot_simulator.stop()
    elif source == "hardware":
        await hardware_bridge.stop()
        
    await close_redis()
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
    app.include_router(crop_profit.router)
    app.include_router(farmer_input_router)
    app.include_router(historical_db_routes.router)
    app.include_router(iot_router)
    app.include_router(chatbot_router, prefix="/chatbot", tags=["chatbot"])

    # ── Global exception handlers ─────────────────────────────────────────
    from fastapi import HTTPException

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
        )

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
