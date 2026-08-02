"""CompliAGL — FastAPI application entry point."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.db.init_db import init_db

# --- Route imports ---
from app.api.routes.health import router as health_router
from app.api.routes.agents import router as agents_router
from app.api.routes.policies import router as policies_router
from app.api.routes.transactions import router as transactions_router
from app.api.routes.approvals import router as approvals_router
from app.api.routes.audit import router as audit_router
from app.api.routes.proofs import router as proofs_router
from app.api.routes.dashboard import router as dashboard_router
# --- Compli402 public API (prefix already set in the router) ---
from app.api.routes.compli402 import router as compli402_router

# --- Canonical v1 API (first-class runtime domain objects) ---
from app.api.v1.router import api_v1_router

# --- MVP 2 route imports (DEPRECATED — in-memory demo surface) ---
from app.mvp2.api.routes.decision import router as mvp2_decision_router
from app.mvp2.api.routes.execution import router as mvp2_execution_router
from app.mvp2.api.routes.proof import router as mvp2_proof_router

# --- Persistent demo seeding ---
from app.core.database import SessionLocal
from app.db.seed import seed_demo_data

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    try:
        init_db()
        logger.info("Database initialised successfully.")
    except Exception:
        logger.exception("Database initialisation failed — tables may be missing.")

    # Seed canonical demo actors and policies into the PERSISTENT database
    # (idempotent — safe on every boot; survives restarts).
    try:
        db = SessionLocal()
        try:
            seed_demo_data(db)
        finally:
            db.close()
        logger.info("Canonical demo actors and policies seeded (persistent).")
    except Exception:
        logger.exception("Persistent seed failed — demo data may be unavailable.")

    print("CompliAGL backend started successfully")
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Agent Governance Layer — policy, identity, and proof engine for agent wallets.",
    lifespan=lifespan,
)

# --- CORS (permissive – hackathon demo) ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Register routers ---
app.include_router(health_router)
app.include_router(agents_router, prefix="/api")
app.include_router(policies_router, prefix="/api")
app.include_router(transactions_router, prefix="/api")
app.include_router(approvals_router, prefix="/api")
app.include_router(audit_router, prefix="/api")
app.include_router(proofs_router, prefix="/api")
app.include_router(dashboard_router, prefix="/api")

# --- MVP 2 routers (prefix already set in each router; DEPRECATED) ---
app.include_router(mvp2_decision_router)
app.include_router(mvp2_execution_router)
app.include_router(mvp2_proof_router)

# --- Compli402 public API (prefix already set in the router) ---
app.include_router(compli402_router)

# --- Canonical v1 API (prefix /api/v1 set on the aggregate router) ---
app.include_router(api_v1_router)


@app.get("/", tags=["root"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
