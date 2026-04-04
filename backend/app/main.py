"""CompliAGL — FastAPI application entry point."""

import os
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown lifecycle hook."""
    init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Agent Governance Layer — policy, identity, and proof engine for agent wallets.",
    lifespan=lifespan,
)

# --- CORS (local dev + Lovable preview) ---
_cors_origins: list[str] = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

# Include Lovable local-preview origin when available
_lovable_origin = os.getenv("LOVABLE_PREVIEW_ORIGIN", "")
if _lovable_origin and _lovable_origin.startswith(("http://", "https://")):
    _cors_origins.append(_lovable_origin)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
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


@app.get("/", tags=["root"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }
