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

# --- MVP 2 route imports ---
from app.mvp2.api.routes.decision import router as mvp2_decision_router
from app.mvp2.api.routes.execution import router as mvp2_execution_router
from app.mvp2.api.routes.proof import router as mvp2_proof_router

# --- MVP 2 seed helpers ---
from app.mvp2.identity.actors import seed_demo_actors
from app.mvp2.core.policy_engine import seed_demo_policies

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    try:
        init_db()
        logger.info("Database initialised successfully.")
    except Exception:
        logger.exception("Database initialisation failed — tables may be missing.")

    # Seed MVP 2 in-memory demo data
    try:
        seed_demo_actors()
        seed_demo_policies()
        logger.info("MVP 2 demo actors and policies seeded.")
    except Exception:
        logger.exception("MVP 2 seed failed — demo data may be unavailable.")

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

# --- MVP 2 routers ---
app.include_router(mvp2_decision_router, prefix="/api/v2")
app.include_router(mvp2_execution_router, prefix="/api/v2")
app.include_router(mvp2_proof_router, prefix="/api/v2")


@app.get("/", tags=["root"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
