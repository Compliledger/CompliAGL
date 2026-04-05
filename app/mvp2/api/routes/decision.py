"""Decision routes for CompliAGL MVP 2.

Provides endpoints for listing actors, listing policies, and evaluating
a transaction against the governance policy bound to the requesting actor.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.mvp2.core.decision_engine import evaluate_transaction
from app.mvp2.core.policy_engine import get_policy_for_actor, list_policies
from app.mvp2.identity.actors import get_actor, list_actors
from app.mvp2.schemas.actor import ActorIdentity
from app.mvp2.schemas.decision import DecisionResult
from app.mvp2.schemas.policy import PolicyDefinition
from app.mvp2.schemas.transaction import TransactionRequest

router = APIRouter(prefix="/api/mvp2", tags=["mvp2-decision"])


@router.get("/actors", response_model=list[ActorIdentity])
def get_actors() -> list[ActorIdentity]:
    """Return all registered actors."""
    return list_actors()


@router.get("/policies", response_model=list[PolicyDefinition])
def get_policies() -> list[PolicyDefinition]:
    """Return all registered policies."""
    return list_policies()


@router.post("/evaluate", response_model=DecisionResult)
def evaluate(request: TransactionRequest) -> DecisionResult:
    """Evaluate a transaction against the actor's governance policy."""
    actor = get_actor(request.actor_id)
    if actor is None:
        raise HTTPException(status_code=404, detail=f"Actor not found: {request.actor_id}")

    policy = get_policy_for_actor(actor.actor_id)
    if policy is None:
        raise HTTPException(status_code=404, detail=f"Policy not found for actor: {actor.actor_id}")

    return evaluate_transaction(request, policy)
