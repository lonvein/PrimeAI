"""FastAPI entry point for construction site machinery monitoring."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from .api.v1.router import router as v1_router
from .core.config import get_settings
from .core.logging import configure_logging
from .db.models import Base  # noqa: F401 — registers all ORM models with metadata
from .db.session import engine

configure_logging()
logger = logging.getLogger(__name__)

settings = get_settings()

# ---------------------------------------------------------------------------
# Create DB tables on startup (idempotent — skips if already exist).
# ---------------------------------------------------------------------------
Base.metadata.create_all(bind=engine)
logger.info("Database tables ready: %s", settings.database_url)

# ---------------------------------------------------------------------------
# Ensure static/debug directory exists.
# ---------------------------------------------------------------------------
debug_dir = settings.static_dir / "debug"
debug_dir.mkdir(parents=True, exist_ok=True)

app = FastAPI(
    title="Build Eye AI — Construction Site Monitoring",
    version="0.2.0",
    description=(
        "Plan vs Fact monitoring for construction sites: "
        "detects machinery in photos and compares against normative schedule requirements."
    ),
)

configure_logging()

app.add_middleware(
    CORSMiddleware,
    # In Docker, frontend is served from same origin via nginx proxy.
    # For local dev we allow both Vite dev server ports.
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount debug images so frontend can fetch annotated photos by URL.
# URL pattern: /static/debug/{uuid}.jpg
app.mount(
    "/static",
    StaticFiles(directory=str(settings.static_dir)),
    name="static",
)

app.include_router(v1_router)

logger.info("Build Eye AI started. YOLO weights: %s", settings.yolo_weights)