"""Evidence layer v1 routes.

These endpoints expose the evidence pipeline and its persistent artifacts:

* ``POST /evidence-collections`` — start evidence collection for a resolution.
* ``GET  /evidence-collections/{job_id}`` — inspect collection status.
* ``GET  /evidence-collections/{job_id}/raw-evidence`` — raw evidence items.
* ``GET  /evidence-collections/{job_id}/validation-results`` — validation results.
* ``GET  /evidence-collections/{job_id}/normalized-evidence`` — normalized evidence.
* ``GET  /evidence-collections/{job_id}/package`` — the Canonical Evidence Package.
* ``GET  /evidence-sources`` — the evidence source registry.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.schemas.canonical.evidence import (
    CanonicalEvidencePackageResponse,
    EvidenceCollectionJobResponse,
    EvidenceOrchestrationPlanResponse,
    EvidenceSourceResponse,
    EvidenceValidationResultResponse,
    NormalizedEvidenceResponse,
    RawEvidenceResponse,
    StartEvidenceCollection,
)
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical.errors import NotFoundError
from app.services.evidence import (
    evidence_collection_service,
    evidence_normalization_service,
    evidence_package_service,
    evidence_source_service,
    evidence_validation_service,
)

router = APIRouter(tags=["v1:evidence"])


# --------------------------------------------------------------------------- #
# Start / status
# --------------------------------------------------------------------------- #
@router.post(
    "/evidence-collections",
    response_model=EvidenceCollectionJobResponse,
    status_code=201,
)
def start_evidence_collection(
    payload: StartEvidenceCollection, db: Session = Depends(get_db)
):
    """Start the end-to-end evidence pipeline for a completed policy resolution."""
    try:
        outcome = evidence_collection_service.start_collection(
            db,
            payload.organization_id,
            payload.policy_resolution_id,
            production_mode=payload.production_mode,
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    return orm_to_dict(outcome.job)


@router.get(
    "/evidence-collections/{job_id}",
    response_model=EvidenceCollectionJobResponse,
)
def get_evidence_collection(
    job_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    job = evidence_collection_service.get_job(db, organization_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="EvidenceCollectionJob not found")
    return orm_to_dict(job)


@router.get(
    "/evidence-collections/{job_id}/plan",
    response_model=EvidenceOrchestrationPlanResponse,
)
def get_evidence_collection_plan(
    job_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    job = evidence_collection_service.get_job(db, organization_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="EvidenceCollectionJob not found")
    plan = evidence_collection_service.get_plan(
        db, organization_id, job.orchestration_plan_id
    )
    if plan is None:
        raise HTTPException(status_code=404, detail="EvidenceOrchestrationPlan not found")
    return orm_to_dict(plan)


# --------------------------------------------------------------------------- #
# Artifacts
# --------------------------------------------------------------------------- #
@router.get(
    "/evidence-collections/{job_id}/raw-evidence",
    response_model=list[RawEvidenceResponse],
)
def list_raw_evidence(
    job_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    job = evidence_collection_service.get_job(db, organization_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="EvidenceCollectionJob not found")
    return [
        orm_to_dict(o)
        for o in evidence_collection_service.list_raw_evidence(
            db, organization_id, job_id
        )
    ]


@router.get(
    "/evidence-collections/{job_id}/validation-results",
    response_model=list[EvidenceValidationResultResponse],
)
def list_validation_results(
    job_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    job = evidence_collection_service.get_job(db, organization_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="EvidenceCollectionJob not found")
    return [
        orm_to_dict(o)
        for o in evidence_validation_service.list_for_job(
            db, organization_id, job_id
        )
    ]


@router.get(
    "/evidence-collections/{job_id}/normalized-evidence",
    response_model=list[NormalizedEvidenceResponse],
)
def list_normalized_evidence(
    job_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    job = evidence_collection_service.get_job(db, organization_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="EvidenceCollectionJob not found")
    return [
        orm_to_dict(o)
        for o in evidence_normalization_service.list_for_job(
            db, organization_id, job_id
        )
    ]


@router.get(
    "/evidence-collections/{job_id}/package",
    response_model=CanonicalEvidencePackageResponse,
)
def get_evidence_package(
    job_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    job = evidence_collection_service.get_job(db, organization_id, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="EvidenceCollectionJob not found")
    package = evidence_package_service.latest_for_evaluation(
        db, organization_id, job.policy_resolution_id
    )
    if package is None:
        raise HTTPException(
            status_code=404, detail="CanonicalEvidencePackage not found"
        )
    return orm_to_dict(package)


# --------------------------------------------------------------------------- #
# Source registry
# --------------------------------------------------------------------------- #
@router.get("/evidence-sources", response_model=list[EvidenceSourceResponse])
def list_evidence_sources(
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [
        orm_to_dict(o)
        for o in evidence_source_service.list_(
            db, organization_id, skip=skip, limit=limit
        )
    ]
