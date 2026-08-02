"""Finding & remediation branch v1 routes.

Exposes the finding-and-remediation lifecycle: list/get/assign findings, create
remediation plans, update remediation status, submit resolution evidence,
validate resolution, trigger re-assessment, DevSync dispatch/callbacks, review
records, and decision history retrieval.
"""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.schemas.canonical.remediation import (
    DecisionHistoryResponse,
    DevSyncCallbackRequest,
    DevSyncDispatchRequest,
    DevSyncDispatchResponse,
    FindingAssignRequest,
    FindingGenerateRequest,
    FindingResponse,
    ReassessmentResponse,
    RemediationPlanCreate,
    RemediationPlanResponse,
    RemediationPlanStatusUpdate,
    ResolutionEvidenceResponse,
    ResolutionEvidenceSubmit,
    ResolutionValidationResponse,
    ReviewRecordCreate,
    ReviewRecordResponse,
)
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical import (
    devsync_service,
    finding_service,
    reassessment_service,
    remediation_service,
    resolution_evidence_service,
    resolution_validation_service,
    review_service,
)
from app.services.canonical.errors import ConflictError, NotFoundError

router = APIRouter(tags=["v1:remediation"])


# --------------------------------------------------------------------------- #
# Findings
# --------------------------------------------------------------------------- #
@router.post("/findings/generate", response_model=list[FindingResponse], status_code=201)
def generate_findings(payload: FindingGenerateRequest, db: Session = Depends(get_db)):
    try:
        findings = finding_service.generate_for_decision(
            db, payload.organization_id, payload.decision_id
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return [orm_to_dict(f) for f in findings]


@router.get("/findings", response_model=list[FindingResponse])
def list_findings(
    status: Optional[str] = None,
    finding_type: Optional[str] = None,
    decision_id: Optional[str] = None,
    intent_id: Optional[str] = None,
    owner: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [
        orm_to_dict(f)
        for f in finding_service.list_(
            db,
            organization_id,
            status=status,
            finding_type=finding_type,
            decision_id=decision_id,
            intent_id=intent_id,
            owner=owner,
            skip=skip,
            limit=limit,
        )
    ]


@router.get("/findings/{resource_id}", response_model=FindingResponse)
def get_finding(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = finding_service.get(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return orm_to_dict(obj)


@router.post("/findings/{resource_id}/assign", response_model=FindingResponse)
def assign_finding(
    resource_id: str,
    payload: FindingAssignRequest,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = finding_service.assign(
        db, organization_id, resource_id, owner=payload.owner, due_date=payload.due_date
    )
    if obj is None:
        raise HTTPException(status_code=404, detail="Finding not found")
    return orm_to_dict(obj)


@router.post(
    "/findings/{resource_id}/validate-resolution",
    response_model=ResolutionValidationResponse,
)
def validate_resolution(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    try:
        return resolution_validation_service.validate(db, organization_id, resource_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/findings/{resource_id}/reassess", response_model=ReassessmentResponse)
def reassess_finding(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    try:
        return reassessment_service.trigger(db, organization_id, resource_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# --------------------------------------------------------------------------- #
# Remediation plans
# --------------------------------------------------------------------------- #
@router.post("/remediation-plans", response_model=RemediationPlanResponse, status_code=201)
def create_remediation_plan(
    payload: RemediationPlanCreate, db: Session = Depends(get_db)
):
    try:
        return orm_to_dict(remediation_service.create_plan(db, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("/remediation-plans/{resource_id}", response_model=RemediationPlanResponse)
def get_remediation_plan(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = remediation_service.get(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="RemediationPlan not found")
    return orm_to_dict(obj)


@router.post(
    "/remediation-plans/{resource_id}/status",
    response_model=RemediationPlanResponse,
)
def update_remediation_status(
    resource_id: str,
    payload: RemediationPlanStatusUpdate,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    try:
        obj = remediation_service.update_status(
            db, organization_id, resource_id, payload.status
        )
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if obj is None:
        raise HTTPException(status_code=404, detail="RemediationPlan not found")
    return orm_to_dict(obj)


# --------------------------------------------------------------------------- #
# Resolution evidence
# --------------------------------------------------------------------------- #
@router.post(
    "/resolution-evidence",
    response_model=ResolutionEvidenceResponse,
    status_code=201,
)
def submit_resolution_evidence(
    payload: ResolutionEvidenceSubmit, db: Session = Depends(get_db)
):
    try:
        return orm_to_dict(resolution_evidence_service.submit(db, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/resolution-evidence/{resource_id}",
    response_model=ResolutionEvidenceResponse,
)
def get_resolution_evidence(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = resolution_evidence_service.get(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="ResolutionEvidence not found")
    return orm_to_dict(obj)


# --------------------------------------------------------------------------- #
# DevSync integration
# --------------------------------------------------------------------------- #
@router.post("/devsync/dispatch", response_model=DevSyncDispatchResponse, status_code=201)
def devsync_dispatch(payload: DevSyncDispatchRequest, db: Session = Depends(get_db)):
    try:
        return orm_to_dict(devsync_service.dispatch(db, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/devsync/callback", response_model=DevSyncDispatchResponse)
def devsync_callback(payload: DevSyncCallbackRequest, db: Session = Depends(get_db)):
    try:
        return orm_to_dict(devsync_service.handle_callback(db, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# --------------------------------------------------------------------------- #
# Review records
# --------------------------------------------------------------------------- #
@router.post("/reviews", response_model=ReviewRecordResponse, status_code=201)
def create_review(payload: ReviewRecordCreate, db: Session = Depends(get_db)):
    try:
        return orm_to_dict(review_service.record(db, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


# --------------------------------------------------------------------------- #
# Decision history
# --------------------------------------------------------------------------- #
@router.get("/decision-history", response_model=DecisionHistoryResponse)
def get_decision_history(
    intent_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    history = reassessment_service.decision_history(db, organization_id, intent_id)
    return {
        "intent_id": history["intent_id"],
        "decisions": history["decisions"],
        "findings": [orm_to_dict(f) for f in history["findings"]],
    }
