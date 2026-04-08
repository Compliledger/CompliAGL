"""MVP 2 decision routes.

Provides endpoints for listing actors, listing policies, and evaluating
a transaction against the governance policies bound to the requesting actor.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.mvp2.core.decision_engine import evaluate
from app.mvp2.core.policy_engine import list_policies
from app.mvp2.identity.actors import get_actor, list_actors
from app.mvp2.schemas.actor import ActorRead
from app.mvp2.schemas.decision import DecisionRequest, DecisionResponse
from app.mvp2.schemas.policy import PolicyRead

router = APIRouter(prefix="/api/mvp2", tags=["mvp2-decision"])


@router.get("/actors", response_model=list[ActorRead])
def get_actors() -> list[ActorRead]:
    """Return all registered actors."""
    return list_actors()


@router.get("/policies", response_model=list[PolicyRead])
def get_policies() -> list[PolicyRead]:
    """Return all registered policies."""
    return list_policies()


@router.post("/evaluate", response_model=DecisionResponse)
def evaluate_decision(request: DecisionRequest) -> DecisionResponse:
    """Evaluate a transaction against all active policies."""
    actor = get_actor(request.actor_id)
    if actor is None:
        raise HTTPException(
            status_code=404,
            detail=f"Actor not found: {request.actor_id}",
        )

    policies = list_policies()
    return evaluate(request=request, policies=policies)
