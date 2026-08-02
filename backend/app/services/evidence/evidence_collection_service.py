"""Evidence collection façade — the end-to-end evidence pipeline.

``start_collection`` runs the whole evidence layer for a completed policy
resolution: it (re)uses the resolved evidence requirement set, builds an
orchestration plan, collects raw evidence via connectors, validates every raw
item, normalizes the valid ones, and assembles the canonical evidence package.
The remaining functions are the read surfaces used by the API.

A caller may inject a custom :class:`ConnectorRegistry` (e.g. real production
connectors, or a test registry). When none is supplied the built-in mock
simulators are used — and are automatically rejected in production mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.canonical_evidence_package import CanonicalEvidencePackage
from app.models.evidence_collection_job import EvidenceCollectionJob
from app.models.evidence_orchestration_plan import EvidenceOrchestrationPlan
from app.repositories.canonical import (
    EvidenceCollectionJobRepository,
    EvidenceOrchestrationPlanRepository,
    RawEvidenceRepository,
)
from app.services.canonical import evidence_requirement_service
from app.services.evidence import (
    evidence_normalization_service,
    evidence_orchestration_service,
    evidence_package_service,
    evidence_source_service,
    evidence_validation_service,
)
from app.services.evidence.connectors import (
    ConnectorRegistry,
    default_simulator_registry,
)


@dataclass
class EvidenceCollectionOutcome:
    """The full set of artifacts produced by one collection run."""

    plan: EvidenceOrchestrationPlan
    job: EvidenceCollectionJob
    package: CanonicalEvidencePackage


def start_collection(
    db: Session,
    organization_id: str,
    policy_resolution_id: str,
    *,
    production_mode: Optional[bool] = None,
    registry: Optional[ConnectorRegistry] = None,
) -> EvidenceCollectionOutcome:
    """Run the end-to-end evidence pipeline for a policy resolution."""
    registry = registry or default_simulator_registry()
    effective_production = evidence_orchestration_service.resolve_production_mode(
        db, organization_id, policy_resolution_id, production_mode
    )

    # Record the available sources for inspection (idempotent).
    evidence_source_service.sync_registry(db, organization_id, registry)

    # (Re)use the resolved evidence requirement set for this resolution.
    evidence_set = evidence_requirement_service.resolve_or_get_for_resolution(
        db, organization_id, policy_resolution_id
    )

    plan = evidence_orchestration_service.build_plan(
        db,
        organization_id,
        evidence_set,
        registry,
        production_mode=effective_production,
    )
    job = evidence_orchestration_service.run_collection(
        db,
        organization_id,
        plan,
        registry,
        production_mode=effective_production,
    )

    # Validate every raw item, then normalize the valid ones.
    raw_items = RawEvidenceRepository(db).list_for_job(organization_id, job.id)
    for raw in raw_items:
        validation = evidence_validation_service.validate_raw_evidence(db, raw)
        evidence_normalization_service.normalize_valid_evidence(
            db, raw, validation
        )

    package = evidence_package_service.build_package(db, organization_id, job)
    return EvidenceCollectionOutcome(plan=plan, job=job, package=package)


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get_job(
    db: Session, organization_id: str, job_id: str
) -> Optional[EvidenceCollectionJob]:
    return EvidenceCollectionJobRepository(db).get(organization_id, job_id)


def get_plan(
    db: Session, organization_id: str, plan_id: str
) -> Optional[EvidenceOrchestrationPlan]:
    return EvidenceOrchestrationPlanRepository(db).get(organization_id, plan_id)


def list_raw_evidence(db: Session, organization_id: str, job_id: str):
    return RawEvidenceRepository(db).list_for_job(organization_id, job_id)
