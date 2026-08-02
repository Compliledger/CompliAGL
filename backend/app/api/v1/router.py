"""Aggregate router for the canonical v1 API."""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    actor_identities,
    governance,
    governance_packages,
    intents,
    operational_contexts,
    targets,
)

api_v1_router = APIRouter(prefix="/api/v1")
api_v1_router.include_router(actor_identities.router)
api_v1_router.include_router(intents.router)
api_v1_router.include_router(targets.router)
api_v1_router.include_router(operational_contexts.router)
api_v1_router.include_router(governance.router)
api_v1_router.include_router(governance_packages.router)
