"""ExecutableGovernancePackage v1 routes — the CompliLedger → CompliAGL contract.

CompliLedger publishes machine-readable, executable governance packages here;
CompliAGL ingests, validates, approves, publishes, retrieves, supersedes, and
retires them. CompliAGL does not reinterpret human-language policy at runtime —
it consumes these approved, versioned, executable packages.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id, require_package_author
from app.core.database import get_db
from app.schemas.canonical.governance_package import (
    ExecutableGovernancePackageCreate,
    ExecutableGovernancePackageResponse,
    PackageApproveRequest,
    PackagePublishRequest,
    PackageSupersedeRequest,
    PackageValidationResult,
)
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical import governance_package_service as svc
from app.services.canonical.errors import (
    AuthorityVerificationError,
    ConflictError,
    InvalidTransitionError,
    NotFoundError,
    PackageImmutableError,
    PackageSignatureError,
)

router = APIRouter(prefix="/governance-packages", tags=["v1:governance-packages"])


@router.post(
    "",
    response_model=ExecutableGovernancePackageResponse,
    status_code=201,
)
def create_package(
    payload: ExecutableGovernancePackageCreate,
    db: Session = Depends(get_db),
    _role: str = Depends(require_package_author),
):
    """Ingest a new executable governance package (DRAFT).

    Restricted to CompliLedger service identities or governance administrators.
    """
    try:
        return orm_to_dict(svc.create(db, payload))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.get("", response_model=list[ExecutableGovernancePackageResponse])
def list_packages(
    package_name: str | None = Query(default=None),
    status: str | None = Query(default=None),
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [
        orm_to_dict(o)
        for o in svc.list_(
            db,
            organization_id,
            package_name=package_name,
            status=status,
            skip=skip,
            limit=limit,
        )
    ]


@router.get(
    "/{package_id}", response_model=ExecutableGovernancePackageResponse
)
def get_package(
    package_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.get(db, organization_id, package_id)
    if obj is None:
        raise HTTPException(
            status_code=404, detail="ExecutableGovernancePackage not found"
        )
    return orm_to_dict(obj)


@router.post(
    "/{package_id}/validate", response_model=PackageValidationResult
)
def validate_package(
    package_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    try:
        result = svc.validate(db, organization_id, package_id)
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except PackageImmutableError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if not result.valid:
        # 422 conveys that the submitted package does not satisfy the contract.
        raise HTTPException(status_code=422, detail=result.model_dump())
    return result


@router.post(
    "/{package_id}/approve",
    response_model=ExecutableGovernancePackageResponse,
)
def approve_package(
    package_id: str,
    payload: PackageApproveRequest,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
    _role: str = Depends(require_package_author),
):
    try:
        return orm_to_dict(
            svc.approve(
                db,
                organization_id,
                package_id,
                approver_principal_id=payload.approver_principal_id,
                rationale=payload.rationale,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except (InvalidTransitionError, ConflictError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except AuthorityVerificationError as exc:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "authority_verification_failed",
                "reason": exc.reason,
                "message": str(exc),
            },
        )


@router.post(
    "/{package_id}/publish",
    response_model=ExecutableGovernancePackageResponse,
)
def publish_package(
    package_id: str,
    payload: PackagePublishRequest | None = None,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
    _role: str = Depends(require_package_author),
):
    expected = payload.expected_package_hash if payload else None
    try:
        return orm_to_dict(
            svc.publish(
                db,
                organization_id,
                package_id,
                expected_package_hash=expected,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except (PackageImmutableError, ConflictError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except PackageSignatureError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/{package_id}/supersede",
    response_model=ExecutableGovernancePackageResponse,
)
def supersede_package(
    package_id: str,
    payload: PackageSupersedeRequest,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
    _role: str = Depends(require_package_author),
):
    try:
        return orm_to_dict(
            svc.supersede(
                db,
                organization_id,
                package_id,
                payload.superseded_by_package_id,
            )
        )
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    except ConflictError as exc:
        raise HTTPException(status_code=409, detail=str(exc))


@router.post(
    "/{package_id}/retire",
    response_model=ExecutableGovernancePackageResponse,
)
def retire_package(
    package_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
    _role: str = Depends(require_package_author),
):
    try:
        return orm_to_dict(svc.retire(db, organization_id, package_id))
    except NotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
