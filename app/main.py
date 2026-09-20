"""
main.py – ChainSleuth FastAPI application entry point.
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import close_neo4j_driver, close_redis, get_neo4j_driver, get_redis
from app.api import routes_trace, routes_cases, routes_fir, routes_notice

settings = get_settings()


# ── Lifespan ──────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle manager."""
    # Startup: eagerly initialise DB connections
    await get_neo4j_driver()
    await get_redis()
    yield
    # Shutdown: gracefully close all connections
    await close_neo4j_driver()
    await close_redis()


# ── Application ───────────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "ChainSleuth – Blockchain forensics and investigation platform for law enforcement. "
        "Trace crypto transactions, detect crime typologies, and generate court-ready FIRs."
    ),
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────

app.include_router(routes_trace.router, prefix="/api/v1")
app.include_router(routes_cases.router, prefix="/api/v1")
app.include_router(routes_fir.router,   prefix="/api/v1")
app.include_router(routes_notice.router, prefix="/api/v1")


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health_check() -> dict:
    """Simple liveness probe."""
    return {"status": "ok", "app": settings.APP_NAME, "version": settings.APP_VERSION}
