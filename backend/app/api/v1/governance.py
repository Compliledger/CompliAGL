"""Governance chain v1 routes: evaluations, decisions, authorizations, results."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.schemas.canonical.governance import (
    DecisionCreate,
    DecisionResponse,
    ExecutionAuthorizationCreate,
    ExecutionAuthorizationResponse,
    ExecutionAuthorizationStatusUpdate,
    ExternalExecutionResultCreate,
    ExternalExecutionResultResponse,
    GovernanceEvaluationCreate,
    GovernanceEvaluationResolve,
    GovernanceEvaluationResponse,
)
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical import governance_service as svc
from app.services.canonical.errors import InvalidTransitionError, NotFoundError

router = APIRouter(tags=["v1:governance"])


# --------------------------------------------------------------------------- #
# GovernanceEvaluation
# --------------------------------------------------------------------------- #
@router.post(
    "/governance-evaluations",
    response_model=GovernanceEvaluationResponse,
    status_code=201,
)
def create_evaluation(
    payload: GovernanceEvaluationCreate, db: Session = Depends(get_db)
):
    try:
        return orm_to_dict(svc.create_evaluation(db, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/governance-evaluations", response_model=list[GovernanceEvaluationResponse]
)
def list_evaluations(
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [
        orm_to_dict(o)
        for o in svc.list_evaluations(db, organization_id, skip=skip, limit=limit)
    ]


@router.get(
    "/governance-evaluations/{resource_id}",
    response_model=GovernanceEvaluationResponse,
)
def get_evaluation(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.get_evaluation(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="GovernanceEvaluation not found")
    return orm_to_dict(obj)


@router.post(
    "/governance-evaluations/{resource_id}/resolve",
    response_model=GovernanceEvaluationResponse,
)
def resolve_evaluation(
    resource_id: str,
    payload: GovernanceEvaluationResolve,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.resolve_evaluation(db, organization_id, resource_id, payload)
    if obj is None:
        raise HTTPException(status_code=404, detail="GovernanceEvaluation not found")
    return orm_to_dict(obj)


# --------------------------------------------------------------------------- #
# Decision
# --------------------------------------------------------------------------- #
@router.post("/decisions", response_model=DecisionResponse, status_code=201)
def create_decision(payload: DecisionCreate, db: Session = Depends(get_db)):
    try:
        return orm_to_dict(svc.create_decision(db, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/decisions", response_model=list[DecisionResponse])
def list_decisions(
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [
        orm_to_dict(o)
        for o in svc.list_decisions(db, organization_id, skip=skip, limit=limit)
    ]


@router.get("/decisions/{resource_id}", response_model=DecisionResponse)
def get_decision(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.get_decision(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Decision not found")
    return orm_to_dict(obj)


# --------------------------------------------------------------------------- #
# ExecutionAuthorization
# --------------------------------------------------------------------------- #
@router.post(
    "/execution-authorizations",
    response_model=ExecutionAuthorizationResponse,
    status_code=201,
)
def create_authorization(
    payload: ExecutionAuthorizationCreate, db: Session = Depends(get_db)
):
    try:
        return orm_to_dict(svc.create_authorization(db, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/execution-authorizations",
    response_model=list[ExecutionAuthorizationResponse],
)
def list_authorizations(
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [
        orm_to_dict(o)
        for o in svc.list_authorizations(db, organization_id, skip=skip, limit=limit)
    ]


@router.get(
    "/execution-authorizations/{resource_id}",
    response_model=ExecutionAuthorizationResponse,
)
def get_authorization(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.get_authorization(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="ExecutionAuthorization not found")
    return orm_to_dict(obj)


@router.post(
    "/execution-authorizations/{resource_id}/transition",
    response_model=ExecutionAuthorizationResponse,
)
def transition_authorization(
    resource_id: str,
    payload: ExecutionAuthorizationStatusUpdate,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    try:
        obj = svc.transition_authorization(
            db, organization_id, resource_id, payload.status
        )
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if obj is None:
        raise HTTPException(status_code=404, detail="ExecutionAuthorization not found")
    return orm_to_dict(obj)


# --------------------------------------------------------------------------- #
# ExternalExecutionResult
# --------------------------------------------------------------------------- #
@router.post(
    "/external-execution-results",
    response_model=ExternalExecutionResultResponse,
    status_code=201,
)
def create_execution_result(
    payload: ExternalExecutionResultCreate, db: Session = Depends(get_db)
):
    try:
        return orm_to_dict(svc.create_execution_result(db, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/external-execution-results",
    response_model=list[ExternalExecutionResultResponse],
)
def list_execution_results(
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [
        orm_to_dict(o)
        for o in svc.list_execution_results(db, organization_id, skip=skip, limit=limit)
    ]


@router.get(
    "/external-execution-results/{resource_id}",
    response_model=ExternalExecutionResultResponse,
)
def get_execution_result(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.get_execution_result(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="ExternalExecutionResult not found")
    return orm_to_dict(obj)
