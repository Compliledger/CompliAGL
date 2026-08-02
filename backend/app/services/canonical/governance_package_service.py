"""ExecutableGovernancePackage service — the CompliLedger → CompliAGL contract.

Implements the package lifecycle (ingest → validate → approve → publish →
supersede/retire) together with the security guarantees required by the
contract:

* Only approved packages may be published.
* Published package contents are immutable — updates require a new version.
* The package hash is recomputed and verified at publish time.
* Signatures are rejected when signing is configured and a signature is invalid.
* Source traceability is preserved (enforced by the JSON-schema/traceability
  validation layer).

No LLM is used anywhere in this module; every decision here is deterministic.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.governance_package import ExecutableGovernancePackage
from app.repositories.canonical import ExecutableGovernancePackageRepository
from app.schemas.canonical.governance_package import (
    ExecutableGovernancePackageCreate,
    PackageValidationResult,
)
from app.schemas.canonical.package_json_schema import validate_package_document
from app.services.canonical.errors import (
    ConflictError,
    NotFoundError,
    PackageImmutableError,
    PackageSignatureError,
)
from app.services.canonical.package_signing import (
    signing_configured,
    verify_signature,
)
from app.services.canonical.transitions import (
    PACKAGE_TRANSITIONS,
    validate_transition,
)
from app.utils.canonical_enums import PackageStatus
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now

# JSON-text content columns on the model.
_CONTENT_FIELDS = (
    "source_document_references",
    "source_requirement_references",
    "requirements",
    "applicability_rules",
    "control_definitions",
    "evidence_requirements",
    "decision_conditions",
    "conflict_resolution_rules",
    "package_metadata",
)


def _dump(value: Any) -> str:
    return json.dumps(value if value is not None else None)


def _load(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


def build_package_document(obj: ExecutableGovernancePackage) -> dict[str, Any]:
    """Return the canonical content document used for validation and hashing."""
    return {
        "package_name": obj.package_name,
        "package_version": obj.package_version,
        "content_schema_version": obj.content_schema_version,
        "effective_at": obj.effective_at.isoformat() if obj.effective_at else None,
        "expires_at": obj.expires_at.isoformat() if obj.expires_at else None,
        "supersedes_package_id": obj.supersedes_package_id,
        "source_document_references": _load(obj.source_document_references) or [],
        "source_requirement_references": _load(obj.source_requirement_references)
        or [],
        "requirements": _load(obj.requirements) or [],
        "applicability_rules": _load(obj.applicability_rules) or [],
        "control_definitions": _load(obj.control_definitions) or [],
        "evidence_requirements": _load(obj.evidence_requirements) or [],
        "decision_conditions": _load(obj.decision_conditions) or [],
        "conflict_resolution_rules": _load(obj.conflict_resolution_rules) or [],
        "metadata": _load(obj.package_metadata) or {},
    }


def compute_package_hash(obj: ExecutableGovernancePackage) -> str:
    """Deterministically hash the immutable content of a package.

    The organization is included so identical content across tenants does not
    collide, and the signature is deliberately excluded (it is *over* the hash).
    """
    payload = {"organization_id": obj.organization_id, **build_package_document(obj)}
    return hash_dict(payload)


# --------------------------------------------------------------------------- #
# Create (ingest)
# --------------------------------------------------------------------------- #
def create(
    db: Session, payload: ExecutableGovernancePackageCreate
) -> ExecutableGovernancePackage:
    """Ingest a new package in DRAFT status and bind its content hash."""
    repo = ExecutableGovernancePackageRepository(db)

    # A published (name, version) pair is immutable — refuse to shadow it.
    existing = repo.get_published(
        payload.organization_id, payload.package_name, payload.package_version
    )
    if existing is not None:
        raise ConflictError(
            f"A PUBLISHED package already exists for "
            f"{payload.package_name} {payload.package_version}; "
            f"publish a new version instead."
        )

    obj = ExecutableGovernancePackage(
        organization_id=payload.organization_id,
        package_name=payload.package_name,
        package_version=payload.package_version,
        content_schema_version=payload.content_schema_version,
        status=PackageStatus.DRAFT.value,
        effective_at=payload.effective_at,
        expires_at=payload.expires_at,
        supersedes_package_id=payload.supersedes_package_id,
        signature=payload.signature,
        signer_key_id=payload.signer_key_id,
        source_document_references=_dump(payload.source_document_references),
        source_requirement_references=_dump(payload.source_requirement_references),
        requirements=_dump(
            [r.model_dump(mode="json") for r in payload.requirements]
        ),
        applicability_rules=_dump(payload.applicability_rules),
        control_definitions=_dump(
            [c.model_dump(mode="json") for c in payload.control_definitions]
        ),
        evidence_requirements=_dump(
            [e.model_dump(mode="json") for e in payload.evidence_requirements]
        ),
        decision_conditions=_dump(
            [d.model_dump(mode="json") for d in payload.decision_conditions]
        ),
        conflict_resolution_rules=_dump(payload.conflict_resolution_rules),
        package_metadata=_dump(payload.metadata),
    )
    obj.package_hash = compute_package_hash(obj)
    return repo.add(obj)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[ExecutableGovernancePackage]:
    return ExecutableGovernancePackageRepository(db).get(organization_id, resource_id)


def list_(
    db: Session,
    organization_id: str,
    *,
    package_name: Optional[str] = None,
    status: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[ExecutableGovernancePackage]:
    return ExecutableGovernancePackageRepository(db).list_filtered(
        organization_id,
        package_name=package_name,
        status=status,
        skip=skip,
        limit=limit,
    )


# --------------------------------------------------------------------------- #
# Lifecycle transitions
# --------------------------------------------------------------------------- #
def _get_or_404(
    db: Session, organization_id: str, resource_id: str
) -> ExecutableGovernancePackage:
    obj = ExecutableGovernancePackageRepository(db).get(organization_id, resource_id)
    if obj is None:
        raise NotFoundError(f"ExecutableGovernancePackage not found: {resource_id}")
    return obj


def validate(
    db: Session, organization_id: str, resource_id: str
) -> PackageValidationResult:
    """Validate a package against the contract and, on success, mark VALIDATED.

    Published/immutable packages cannot be re-validated. On validation failure
    the package remains in its current status and the errors are returned.
    """
    repo = ExecutableGovernancePackageRepository(db)
    obj = _get_or_404(db, organization_id, resource_id)

    if obj.status not in (
        PackageStatus.DRAFT.value,
        PackageStatus.VALIDATED.value,
    ):
        raise PackageImmutableError(
            f"Package in status {obj.status} cannot be validated"
        )

    document = build_package_document(obj)
    errors = validate_package_document(document)
    if errors:
        return PackageValidationResult(
            valid=False, errors=errors, status=obj.status
        )

    if obj.status == PackageStatus.DRAFT.value:
        validate_transition(
            "ExecutableGovernancePackage",
            PACKAGE_TRANSITIONS,
            obj.status,
            PackageStatus.VALIDATED.value,
        )
        obj.status = PackageStatus.VALIDATED.value
        # Re-bind the hash to the validated content.
        obj.package_hash = compute_package_hash(obj)
        repo.save(obj)

    return PackageValidationResult(valid=True, errors=[], status=obj.status)


def approve(
    db: Session, organization_id: str, resource_id: str, approved_by: str
) -> ExecutableGovernancePackage:
    """Approve a VALIDATED package. Only approved packages may be published."""
    repo = ExecutableGovernancePackageRepository(db)
    obj = _get_or_404(db, organization_id, resource_id)
    validate_transition(
        "ExecutableGovernancePackage",
        PACKAGE_TRANSITIONS,
        obj.status,
        PackageStatus.APPROVED.value,
    )
    obj.status = PackageStatus.APPROVED.value
    obj.approved_by = approved_by
    obj.approved_at = utc_now()
    return repo.save(obj)


def publish(
    db: Session,
    organization_id: str,
    resource_id: str,
    *,
    expected_package_hash: Optional[str] = None,
) -> ExecutableGovernancePackage:
    """Publish an APPROVED package.

    Recomputes and verifies the package hash (immutability), verifies the
    signature when signing is configured, then makes the package the active
    PUBLISHED version. If the package supersedes another, that package is moved
    to SUPERSEDED atomically.
    """
    repo = ExecutableGovernancePackageRepository(db)
    obj = _get_or_404(db, organization_id, resource_id)

    validate_transition(
        "ExecutableGovernancePackage",
        PACKAGE_TRANSITIONS,
        obj.status,
        PackageStatus.PUBLISHED.value,
    )

    # Recompute and verify the hash — published content must be immutable.
    recomputed = compute_package_hash(obj)
    if obj.package_hash and obj.package_hash != recomputed:
        raise PackageImmutableError(
            "Package hash mismatch — contents changed after approval"
        )
    if expected_package_hash is not None and expected_package_hash != recomputed:
        raise PackageImmutableError(
            "Package hash does not match the expected hash supplied at publish"
        )
    obj.package_hash = recomputed

    # Reject invalid signatures when signing is configured (or when a signer
    # is declared on the package).
    if signing_configured() or obj.signer_key_id:
        if not verify_signature(obj.signer_key_id, obj.package_hash, obj.signature):
            raise PackageSignatureError(
                "Invalid or missing package signature for "
                f"signer_key_id={obj.signer_key_id!r}"
            )

    # Enforce uniqueness of the active PUBLISHED (name, version).
    already = repo.get_published(
        organization_id, obj.package_name, obj.package_version
    )
    if already is not None and already.id != obj.id:
        raise ConflictError(
            f"A PUBLISHED package already exists for "
            f"{obj.package_name} {obj.package_version}"
        )

    # Supersede the referenced predecessor, if any.
    if obj.supersedes_package_id:
        predecessor = repo.get(organization_id, obj.supersedes_package_id)
        if predecessor is None:
            raise NotFoundError(
                f"supersedes_package_id not found: {obj.supersedes_package_id}"
            )
        if predecessor.status == PackageStatus.PUBLISHED.value:
            validate_transition(
                "ExecutableGovernancePackage",
                PACKAGE_TRANSITIONS,
                predecessor.status,
                PackageStatus.SUPERSEDED.value,
            )
            predecessor.status = PackageStatus.SUPERSEDED.value
            predecessor.superseded_by_package_id = obj.id
            db.add(predecessor)

    obj.status = PackageStatus.PUBLISHED.value
    obj.published_at = utc_now()
    return repo.save(obj)


def supersede(
    db: Session,
    organization_id: str,
    resource_id: str,
    superseded_by_package_id: str,
) -> ExecutableGovernancePackage:
    """Mark a PUBLISHED package as SUPERSEDED by another (published) package."""
    repo = ExecutableGovernancePackageRepository(db)
    obj = _get_or_404(db, organization_id, resource_id)

    successor = repo.get(organization_id, superseded_by_package_id)
    if successor is None:
        raise NotFoundError(
            f"superseded_by_package_id not found: {superseded_by_package_id}"
        )
    if successor.id == obj.id:
        raise ConflictError("A package cannot supersede itself")

    validate_transition(
        "ExecutableGovernancePackage",
        PACKAGE_TRANSITIONS,
        obj.status,
        PackageStatus.SUPERSEDED.value,
    )
    obj.status = PackageStatus.SUPERSEDED.value
    obj.superseded_by_package_id = superseded_by_package_id
    return repo.save(obj)


def retire(
    db: Session, organization_id: str, resource_id: str
) -> ExecutableGovernancePackage:
    """Retire a PUBLISHED or SUPERSEDED package."""
    repo = ExecutableGovernancePackageRepository(db)
    obj = _get_or_404(db, organization_id, resource_id)
    validate_transition(
        "ExecutableGovernancePackage",
        PACKAGE_TRANSITIONS,
        obj.status,
        PackageStatus.RETIRED.value,
    )
    obj.status = PackageStatus.RETIRED.value
    return repo.save(obj)


# --------------------------------------------------------------------------- #
# Runtime retrieval helper
# --------------------------------------------------------------------------- #
def get_published_version(
    db: Session, organization_id: str, package_name: str, package_version: str
) -> Optional[ExecutableGovernancePackage]:
    """Return the PUBLISHED package for the requested name + version.

    This is the entry point runtime services use to fetch the correct executable
    governance to apply — never a DRAFT/APPROVED/SUPERSEDED/RETIRED package.
    """
    return ExecutableGovernancePackageRepository(db).get_published(
        organization_id, package_name, package_version
    )
