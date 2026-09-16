"""Real reset of one organization's Demo #3 run data.

Deletes every canonical *run* record CompliAGL has produced for one
organization -- Target/Intent through Decision/EscalationApproval/
ExecutionAuthorization/ExternalExecutionResult/CanonicalAIProof, and every
intermediate evidence/assessment/finding record in between -- so a fresh
run through the Demo #3 flow starts from a clean slate instead of the
frontend (or a driver script) having to work around leftover state from a
previous run.

Deliberately **not** deleted: :class:`~app.models.organization.Organization`,
:class:`~app.models.actor_identity.ActorIdentity` (AIRA / SENTRY / Jordan),
:class:`~app.models.governance_package.ExecutableGovernancePackage` (the
published HarborStone / Hedera-demo packages), and
:class:`~app.models.evidence_source.EvidenceSource` (the connector
registry). Those are infrastructure that ``app.db.seed.seed_demo_data``
idempotently (re)provisions on every boot, not per-run data -- deleting and
relying on a reboot to restore them would make Reset asynchronous and
order-dependent for no benefit; every model deleted here is pure per-run
output with no seed step that recreates it.

Every model here shares :class:`~app.models._mixins.CanonicalMixin`, so
every row is already tagged with the ``organization_id`` this delete scopes
to -- another organization's data is never touched.
"""

from __future__ import annotations

from typing import Type

from sqlalchemy.orm import Session

from app.core.database import Base
from app.models.applicability_evaluation import ApplicabilityEvaluation
from app.models.applicable_control_set import ApplicableControlSet
from app.models.assessment import Assessment
from app.models.canonical_aiproof import CanonicalAIProof
from app.models.canonical_evidence_package import CanonicalEvidencePackage
from app.models.control_evaluation import ControlEvaluation
from app.models.decision import Decision
from app.models.devsync_dispatch import DevSyncDispatch
from app.models.escalation_approval import EscalationApproval
from app.models.event_delivery import EventDelivery
from app.models.evidence_collection_job import EvidenceCollectionJob
from app.models.evidence_orchestration_plan import EvidenceOrchestrationPlan
from app.models.evidence_requirement_set import EvidenceRequirementSet
from app.models.evidence_sufficiency import EvidenceSufficiency
from app.models.evidence_validation_result import EvidenceValidationResult
from app.models.execution_authorization import ExecutionAuthorization
from app.models.external_execution_result import ExternalExecutionResult
from app.models.finding import Finding
from app.models.governance_evaluation import GovernanceEvaluation
from app.models.integration_event import IntegrationEvent
from app.models.intent import Intent
from app.models.monitoring_event import MonitoringEvent
from app.models.normalized_evidence import NormalizedEvidence
from app.models.operational_context import OperationalContext
from app.models.policy_resolution import PolicyResolution
from app.models.raw_evidence import RawEvidence
from app.models.reevaluation_run import ReevaluationRun
from app.models.remediation_plan import RemediationPlan
from app.models.resolution_evidence import ResolutionEvidence
from app.models.review_record import ReviewRecord
from app.models.target import Target

# Deletion order matters only for readability here -- none of these columns
# are declared as real SQLAlchemy/DB ``ForeignKey``s (every cross-record
# reference in the canonical model is a plain, unconstrained id column), so
# there is no FK-driven ordering requirement. Listed leaf-to-root anyway.
_RUN_DATA_MODELS: tuple[Type[Base], ...] = (
    CanonicalAIProof,
    ExternalExecutionResult,
    ExecutionAuthorization,
    EscalationApproval,
    Finding,
    RemediationPlan,
    ResolutionEvidence,
    ReviewRecord,
    Decision,
    Assessment,
    ControlEvaluation,
    EvidenceSufficiency,
    NormalizedEvidence,
    EvidenceValidationResult,
    RawEvidence,
    CanonicalEvidencePackage,
    EvidenceCollectionJob,
    EvidenceOrchestrationPlan,
    ApplicableControlSet,
    EvidenceRequirementSet,
    ApplicabilityEvaluation,
    PolicyResolution,
    GovernanceEvaluation,
    OperationalContext,
    Intent,
    Target,
    MonitoringEvent,
    ReevaluationRun,
    DevSyncDispatch,
    IntegrationEvent,
    EventDelivery,
)


def reset_demo_state(db: Session, organization_id: str) -> dict[str, int]:
    """Delete every per-run canonical record for ``organization_id``.

    Returns the number of rows deleted per model name, so a caller (or a
    test) can see exactly what was cleared rather than trusting a bare
    "ok". Runs as one transaction: either every table is cleared and
    committed, or nothing is (a mid-loop failure rolls back the whole
    reset rather than leaving it half-applied).
    """
    if not organization_id:
        raise ValueError("organization_id is required")

    deleted: dict[str, int] = {}
    try:
        for model in _RUN_DATA_MODELS:
            count = (
                db.query(model)
                .filter(model.organization_id == organization_id)  # type: ignore[attr-defined]
                .delete(synchronize_session=False)
            )
            deleted[model.__tablename__] = count  # type: ignore[attr-defined]
        db.commit()
    except Exception:
        db.rollback()
        raise
    return deleted
