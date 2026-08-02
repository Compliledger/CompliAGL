"""Deterministic Decision engine + signed Execution Authorization v1 routes.

These routes expose the canonical Decision stage and the signed
ExecutionAuthorization resource:

* run the deterministic decision engine for a resolved evaluation,
* retrieve / explain a decision,
* issue, verify, revoke and consume a signed execution authorization.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.schemas.canonical.governance import (
    DecideFromResolutionRequest,
    DecisionResponse,
    ExecutionAuthorizationIssueRequest,
    ExecutionAuthorizationResponse,
    ExecutionAuthorizationRevokeRequest,
    ExecutionAuthorizationVerifyRequest,
    ExecutionAuthorizationVerifyResponse,
)
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical import authorization_service, decision_service
from app.services.canonical.errors import ConflictError, NotFoundError

router = APIRouter(tags=["v1:decision-authorization"])


# --------------------------------------------------------------------------- #
# Decision engine
# --------------------------------------------------------------------------- #
@router.post("/decisions/decide", response_model=DecisionResponse, status_code=201)
def decide(payload: DecideFromResolutionRequest, db: Session = Depends(get_db)):
    """Run the deterministic decision engine for a resolved evaluation."""
    try:
        decision = decision_service.decide_for_resolution(
            db,
            payload.organization_id,
            payload.policy_resolution_id,
            prior_decision_id=payload.prior_decision_id,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return orm_to_dict(decision)


@router.get("/decisions/{resource_id}/explain")
def explain_decision(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Return a structured, auditable explanation of a decision."""
    explanation = decision_service.explain(db, organization_id, resource_id)
    if explanation is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return explanation


# --------------------------------------------------------------------------- #
# Signed execution authorization
# --------------------------------------------------------------------------- #
@router.post(
    "/execution-authorizations/issue",
    response_model=ExecutionAuthorizationResponse,
    status_code=201,
)
def issue_authorization(
    payload: ExecutionAuthorizationIssueRequest, db: Session = Depends(get_db)
):
    """Issue a signed authorization for an APPROVED decision."""
    try:
        auth = authorization_service.issue(
            db,
            payload.organization_id,
            payload.decision_id,
            permitted_execution_system=payload.permitted_execution_system,
            authorized_parameter_constraints=payload.authorized_parameter_constraints,
            max_amount_minor=payload.max_amount_minor,
            max_amount_currency=payload.max_amount_currency,
            expires_at=payload.expires_at,
            idempotency_key=payload.idempotency_key,
            one_time_use=payload.one_time_use,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return orm_to_dict(auth)


@router.post(
    "/execution-authorizations/{resource_id}/verify",
    response_model=ExecutionAuthorizationVerifyResponse,
)
def verify_authorization(
    resource_id: str,
    payload: ExecutionAuthorizationVerifyRequest | None = None,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Independently verify a signed authorization before execution."""
    payload = payload or ExecutionAuthorizationVerifyRequest()
    result = authorization_service.verify(
        db,
        organization_id,
        resource_id,
        expected_fields=payload.expected_fields,
        activate=payload.activate,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="ExecutionAuthorization not found")
    return result


@router.post(
    "/execution-authorizations/{resource_id}/consume",
    response_model=ExecutionAuthorizationResponse,
)
def consume_authorization(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Consume a one-time-use authorization (replay-protected)."""
    try:
        auth = authorization_service.consume(db, organization_id, resource_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return orm_to_dict(auth)


@router.post(
    "/execution-authorizations/{resource_id}/revoke",
    response_model=ExecutionAuthorizationResponse,
)
def revoke_authorization(
    resource_id: str,
    payload: ExecutionAuthorizationRevokeRequest | None = None,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Revoke a live authorization."""
    payload = payload or ExecutionAuthorizationRevokeRequest()
    try:
        auth = authorization_service.revoke(
            db, organization_id, resource_id, reason=payload.reason
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return orm_to_dict(auth)
