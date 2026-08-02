"""Policy Resolution and Applicability Evaluation v1 routes.

These endpoints expose the two deterministic runtime stages that precede the
decision engine and the APIs to retrieve their persistent results:

* ``/policy-resolutions`` — run and retrieve Policy Resolution records.
* ``/applicability-evaluations`` — run and retrieve per-requirement
  Applicability Evaluation records.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.schemas.canonical.control_evidence import (
    ApplicableControlSetResponse,
    ControlDeterminationCreate,
    EvidenceRequirementResolutionCreate,
    EvidenceRequirementSetResponse,
)
from app.schemas.canonical.policy_applicability import (
    ApplicabilityEvaluationCreate,
    ApplicabilityEvaluationResponse,
    PolicyResolutionCreate,
    PolicyResolutionResponse,
)
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical import (
    applicability_service,
    control_determination_service,
    evidence_requirement_service,
    policy_resolution_service,
)
from app.services.canonical.errors import NotFoundError

router = APIRouter(tags=["v1:policy-resolution"])


# --------------------------------------------------------------------------- #
# Policy Resolution
# --------------------------------------------------------------------------- #
@router.post(
    "/policy-resolutions",
    response_model=PolicyResolutionResponse,
    status_code=201,
)
def create_policy_resolution(
    payload: PolicyResolutionCreate, db: Session = Depends(get_db)
):
    """Run the deterministic Policy Resolution stage and persist the record."""
    try:
        return orm_to_dict(policy_resolution_service.resolve(db, payload))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/policy-resolutions", response_model=list[PolicyResolutionResponse]
)
def list_policy_resolutions(
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [
        orm_to_dict(o)
        for o in policy_resolution_service.list_(
            db, organization_id, skip=skip, limit=limit
        )
    ]


@router.get(
    "/policy-resolutions/{resource_id}",
    response_model=PolicyResolutionResponse,
)
def get_policy_resolution(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = policy_resolution_service.get(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="PolicyResolution not found")
    return orm_to_dict(obj)


# --------------------------------------------------------------------------- #
# Applicability Evaluation
# --------------------------------------------------------------------------- #
@router.post(
    "/applicability-evaluations",
    response_model=list[ApplicabilityEvaluationResponse],
    status_code=201,
)
def create_applicability_evaluations(
    payload: ApplicabilityEvaluationCreate, db: Session = Depends(get_db)
):
    """Evaluate every candidate requirement for a resolution and persist results."""
    try:
        results = applicability_service.evaluate_for_resolution(db, payload)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return [orm_to_dict(o) for o in results]


@router.get(
    "/applicability-evaluations",
    response_model=list[ApplicabilityEvaluationResponse],
)
def list_applicability_evaluations(
    policy_resolution_id: str | None = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [
        orm_to_dict(o)
        for o in applicability_service.list_(
            db,
            organization_id,
            policy_resolution_id=policy_resolution_id,
            skip=skip,
            limit=limit,
        )
    ]


@router.get(
    "/applicability-evaluations/{resource_id}",
    response_model=ApplicabilityEvaluationResponse,
)
def get_applicability_evaluation(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = applicability_service.get(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(
            status_code=404, detail="ApplicabilityEvaluation not found"
        )
    return orm_to_dict(obj)


# --------------------------------------------------------------------------- #
# Control Determination
#
# ``evaluation_id`` identifies the applicability-evaluation run — i.e. the
# ``policy_resolution_id`` whose per-requirement ApplicabilityEvaluation records
# these stages consume. Control Determination and Evidence Requirement
# Resolution are computed deterministically on demand and persisted, so a GET
# materialises the set the first time it is requested.
# --------------------------------------------------------------------------- #
@router.post(
    "/control-determinations",
    response_model=ApplicableControlSetResponse,
    status_code=201,
)
def create_control_determination(
    payload: ControlDeterminationCreate, db: Session = Depends(get_db)
):
    """Run Control Determination for a resolution and persist the control set."""
    try:
        return orm_to_dict(
            control_determination_service.determine_for_resolution(db, payload)
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/evaluations/{evaluation_id}/controls",
    response_model=ApplicableControlSetResponse,
)
def get_evaluation_controls(
    evaluation_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Return the applicable controls determined for an evaluation."""
    if policy_resolution_service.get(db, organization_id, evaluation_id) is None:
        raise HTTPException(status_code=404, detail="PolicyResolution not found")
    obj = control_determination_service.determine_or_get_for_resolution(
        db, organization_id, evaluation_id
    )
    return orm_to_dict(obj)


# --------------------------------------------------------------------------- #
# Evidence Requirement Resolution
# --------------------------------------------------------------------------- #
@router.post(
    "/evidence-requirement-resolutions",
    response_model=EvidenceRequirementSetResponse,
    status_code=201,
)
def create_evidence_requirement_resolution(
    payload: EvidenceRequirementResolutionCreate, db: Session = Depends(get_db)
):
    """Run Evidence Requirement Resolution and persist the evidence set."""
    try:
        return orm_to_dict(
            evidence_requirement_service.resolve_for_resolution(db, payload)
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/evaluations/{evaluation_id}/evidence-requirements",
    response_model=EvidenceRequirementSetResponse,
)
def get_evaluation_evidence_requirements(
    evaluation_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    """Return the evidence requirements resolved for an evaluation."""
    if policy_resolution_service.get(db, organization_id, evaluation_id) is None:
        raise HTTPException(status_code=404, detail="PolicyResolution not found")
    obj = evidence_requirement_service.resolve_or_get_for_resolution(
        db, organization_id, evaluation_id
    )
    return orm_to_dict(obj)
