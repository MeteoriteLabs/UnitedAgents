"""United Agents — FastAPI application factory.

Core application with health check, CORS, and router mounting.
Product routes are added in subsequent sessions.
"""

import os
import logging
from contextlib import asynccontextmanager

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Configure logging
log_level = os.environ.get("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, log_level, logging.INFO),
    format="%(asctime)s %(name)s %(levelname)s %(message)s",
)
logger = logging.getLogger("united_agents")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    logger.info("United Agents backend starting up")
    yield
    logger.info("United Agents backend shutting down")


app = FastAPI(
    title="United Agents",
    description="AI Agents Assembly for Global Causes",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — per D-15 / GOTCHAS 1.4: never use * with credentials
cors_origins_raw = os.environ.get("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000")
cors_origins = [o.strip() for o in cors_origins_raw.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok", "service": "united-agents"}


@app.get("/api/v1/health")
async def api_health():
    """API health check."""
    return {"status": "ok", "service": "united-agents", "version": "0.1.0"}


def run():
    """Entrypoint for run.py."""
    import uvicorn
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run("src.main:app", host="0.0.0.0", port=port, reload=True)
