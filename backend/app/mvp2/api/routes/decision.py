"""MVP 2 decision routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.mvp2.core.decision_engine import evaluate
from app.mvp2.schemas.decision import DecisionRequest, DecisionResponse
from app.mvp2.schemas.policy import PolicyRead

router = APIRouter(prefix="/decisions", tags=["mvp2-decisions"])


@router.post("/", response_model=DecisionResponse)
async def create_decision(request: DecisionRequest) -> DecisionResponse:
    """Evaluate a transaction against all active policies.

    .. note::

        In a production deployment the route would load policies from a
        persistent store.  For MVP 2 we pass an empty list so the
        endpoint is callable end-to-end.
    """
    policies: list[PolicyRead] = []  # TODO: load from database
    return evaluate(request=request, policies=policies)
