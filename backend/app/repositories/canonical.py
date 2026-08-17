"""Tenant-scoped repositories for canonical first-class resources.

The :class:`TenantRepository` base guarantees that every read/list/count query
is filtered by ``organization_id``. Callers must always pass the tenant, so a
missing or mismatched tenant can never leak another organization's data.
"""

from __future__ import annotations

from typing import Generic, Optional, Sequence, Type, TypeVar

from sqlalchemy.orm import Session

from app.models.actor_identity import ActorIdentity
from app.models.applicability_evaluation import ApplicabilityEvaluation
from app.models.applicable_control_set import ApplicableControlSet
from app.models.canonical_aiproof import CanonicalAIProof
from app.models.decision import Decision
from app.models.evidence_requirement_set import EvidenceRequirementSet
from app.models.evidence_source import EvidenceSource
from app.models.evidence_orchestration_plan import EvidenceOrchestrationPlan
from app.models.evidence_collection_job import EvidenceCollectionJob
from app.models.raw_evidence import RawEvidence
from app.models.evidence_validation_result import EvidenceValidationResult
from app.models.normalized_evidence import NormalizedEvidence
from app.models.canonical_evidence_package import CanonicalEvidencePackage
from app.models.evidence_sufficiency import EvidenceSufficiency
from app.models.control_evaluation import ControlEvaluation
from app.models.assessment import Assessment
from app.models.finding import Finding
from app.models.remediation_plan import RemediationPlan
from app.models.resolution_evidence import ResolutionEvidence
from app.models.devsync_dispatch import DevSyncDispatch
from app.models.event_delivery import EventDelivery
from app.models.integration_event import IntegrationEvent
from app.models.review_record import ReviewRecord
from app.models.execution_authorization import ExecutionAuthorization
from app.models.external_execution_result import ExternalExecutionResult
from app.models.governance_evaluation import GovernanceEvaluation
from app.models.governance_package import ExecutableGovernancePackage
from app.models.intent import Intent
from app.models.operational_context import OperationalContext
from app.models.monitoring_event import MonitoringEvent
from app.models.reevaluation_run import ReevaluationRun
from app.models.policy_resolution import PolicyResolution
from app.models.target import Target
from app.services.canonical import organization_service

ModelT = TypeVar("ModelT")


class TenantRepository(Generic[ModelT]):
    """Base repository enforcing tenant isolation on every query."""

    model: Type[ModelT]

    def __init__(self, db: Session) -> None:
        self.db = db

    # -- internal ---------------------------------------------------------- #
    def _scoped(self, organization_id: str):
        """Return a base query already filtered to the tenant."""
        if not organization_id:
            raise ValueError("organization_id is required for tenant isolation")
        organization_service.require_active(self.db, organization_id)
        return self.db.query(self.model).filter(
            self.model.organization_id == organization_id  # type: ignore[attr-defined]
        )

    # -- reads ------------------------------------------------------------- #
    def get(self, organization_id: str, resource_id: str) -> Optional[ModelT]:
        return (
            self._scoped(organization_id)
            .filter(self.model.id == resource_id)  # type: ignore[attr-defined]
            .first()
        )

    def list(
        self, organization_id: str, *, skip: int = 0, limit: int = 100
    ) -> Sequence[ModelT]:
        return (
            self._scoped(organization_id)
            .order_by(self.model.created_at.asc())  # type: ignore[attr-defined]
            .offset(skip)
            .limit(limit)
            .all()
        )

    def count(self, organization_id: str) -> int:
        return self._scoped(organization_id).count()

    def find_one(self, organization_id: str, **filters) -> Optional[ModelT]:
        """Return the first row in the tenant matching equality ``filters``."""
        query = self._scoped(organization_id)
        for attribute, value in filters.items():
            query = query.filter(getattr(self.model, attribute) == value)
        return query.first()

    # -- writes ------------------------------------------------------------ #
    def add(self, obj: ModelT) -> ModelT:
        organization_service.require_active(
            self.db, obj.organization_id  # type: ignore[attr-defined]
        )
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def save(self, obj: ModelT) -> ModelT:
        """Persist in-place mutations to an already-tracked instance."""
        self.db.commit()
        self.db.refresh(obj)
        return obj


class ActorIdentityRepository(TenantRepository[ActorIdentity]):
    model = ActorIdentity


class IntentRepository(TenantRepository[Intent]):
    model = Intent


class TargetRepository(TenantRepository[Target]):
    model = Target


class OperationalContextRepository(TenantRepository[OperationalContext]):
    model = OperationalContext


class GovernanceEvaluationRepository(TenantRepository[GovernanceEvaluation]):
    model = GovernanceEvaluation

    def list_for_intent(
        self,
        organization_id: str,
        intent_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[GovernanceEvaluation]:
        return (
            self._scoped(organization_id)
            .filter(self.model.intent_id == intent_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )


class DecisionRepository(TenantRepository[Decision]):
    model = Decision

    def current_for_evaluation(
        self, organization_id: str, evaluation_id: str
    ) -> Optional[Decision]:
        """Return the current (non-superseded) decision for an evaluation."""
        from app.utils.canonical_enums import DecisionSupersessionStatus

        return (
            self._scoped(organization_id)
            .filter(self.model.evaluation_id == evaluation_id)
            .filter(
                self.model.supersession_status
                == DecisionSupersessionStatus.CURRENT.value
            )
            .order_by(self.model.created_at.desc())
            .first()
        )

    def list_for_evaluation(
        self,
        organization_id: str,
        evaluation_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Decision]:
        return (
            self._scoped(organization_id)
            .filter(self.model.evaluation_id == evaluation_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_for_intent(
        self,
        organization_id: str,
        intent_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Decision]:
        return (
            self._scoped(organization_id)
            .filter(self.model.intent_id == intent_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def current_for_intent(
        self, organization_id: str, intent_id: str
    ) -> Optional[Decision]:
        """Return the current (non-superseded) decision for an intent."""
        from app.utils.canonical_enums import DecisionSupersessionStatus

        return (
            self._scoped(organization_id)
            .filter(self.model.intent_id == intent_id)
            .filter(
                self.model.supersession_status
                == DecisionSupersessionStatus.CURRENT.value
            )
            .order_by(self.model.created_at.desc())
            .first()
        )


class ExecutionAuthorizationRepository(TenantRepository[ExecutionAuthorization]):
    model = ExecutionAuthorization

    def get_by_idempotency_key(
        self, organization_id: str, idempotency_key: str
    ) -> Optional[ExecutionAuthorization]:
        """Return an existing authorization for an idempotency key, if any."""
        if not idempotency_key:
            return None
        return (
            self._scoped(organization_id)
            .filter(self.model.idempotency_key == idempotency_key)
            .order_by(self.model.created_at.asc())
            .first()
        )

    def list_for_decision(
        self,
        organization_id: str,
        decision_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ExecutionAuthorization]:
        return (
            self._scoped(organization_id)
            .filter(self.model.decision_id == decision_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_for_intent(
        self,
        organization_id: str,
        intent_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ExecutionAuthorization]:
        return (
            self._scoped(organization_id)
            .filter(self.model.intent_id == intent_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )


class ExternalExecutionResultRepository(TenantRepository[ExternalExecutionResult]):
    model = ExternalExecutionResult


class ExecutableGovernancePackageRepository(
    TenantRepository[ExecutableGovernancePackage]
):
    model = ExecutableGovernancePackage

    def list_filtered(
        self,
        organization_id: str,
        *,
        package_name: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ExecutableGovernancePackage]:
        """List packages in the tenant, optionally filtered by name/status."""
        query = self._scoped(organization_id)
        if package_name is not None:
            query = query.filter(self.model.package_name == package_name)
        if status is not None:
            query = query.filter(self.model.status == status)
        return (
            query.order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_published(
        self, organization_id: str, package_name: str, package_version: str
    ) -> Optional[ExecutableGovernancePackage]:
        """Return the PUBLISHED package for a given name + version, if any."""
        from app.utils.canonical_enums import PackageStatus

        return (
            self._scoped(organization_id)
            .filter(self.model.package_name == package_name)
            .filter(self.model.package_version == package_version)
            .filter(self.model.status == PackageStatus.PUBLISHED.value)
            .first()
        )


class PolicyResolutionRepository(TenantRepository[PolicyResolution]):
    model = PolicyResolution


class ApplicabilityEvaluationRepository(
    TenantRepository[ApplicabilityEvaluation]
):
    model = ApplicabilityEvaluation

    def list_for_resolution(
        self,
        organization_id: str,
        policy_resolution_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ApplicabilityEvaluation]:
        """List applicability results for one policy resolution, in order."""
        return (
            self._scoped(organization_id)
            .filter(self.model.policy_resolution_id == policy_resolution_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )


class ApplicableControlSetRepository(TenantRepository[ApplicableControlSet]):
    model = ApplicableControlSet

    def latest_for_resolution(
        self, organization_id: str, policy_resolution_id: str
    ) -> Optional[ApplicableControlSet]:
        """Return the most recent control set for a policy resolution, if any."""
        return (
            self._scoped(organization_id)
            .filter(self.model.policy_resolution_id == policy_resolution_id)
            .order_by(self.model.created_at.desc())
            .first()
        )

    def list_for_resolution(
        self,
        organization_id: str,
        policy_resolution_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ApplicableControlSet]:
        return (
            self._scoped(organization_id)
            .filter(self.model.policy_resolution_id == policy_resolution_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )


class EvidenceRequirementSetRepository(
    TenantRepository[EvidenceRequirementSet]
):
    model = EvidenceRequirementSet

    def latest_for_resolution(
        self, organization_id: str, policy_resolution_id: str
    ) -> Optional[EvidenceRequirementSet]:
        """Return the most recent evidence set for a policy resolution, if any."""
        return (
            self._scoped(organization_id)
            .filter(self.model.policy_resolution_id == policy_resolution_id)
            .order_by(self.model.created_at.desc())
            .first()
        )

    def list_for_resolution(
        self,
        organization_id: str,
        policy_resolution_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[EvidenceRequirementSet]:
        return (
            self._scoped(organization_id)
            .filter(self.model.policy_resolution_id == policy_resolution_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )


# --------------------------------------------------------------------------- #
# Evidence layer repositories
# --------------------------------------------------------------------------- #
class EvidenceSourceRepository(TenantRepository[EvidenceSource]):
    model = EvidenceSource

    def get_by_connector_id(
        self, organization_id: str, connector_id: str
    ) -> Optional[EvidenceSource]:
        return self.find_one(organization_id, connector_id=connector_id)


class EvidenceOrchestrationPlanRepository(
    TenantRepository[EvidenceOrchestrationPlan]
):
    model = EvidenceOrchestrationPlan

    def latest_for_resolution(
        self, organization_id: str, policy_resolution_id: str
    ) -> Optional[EvidenceOrchestrationPlan]:
        return (
            self._scoped(organization_id)
            .filter(self.model.policy_resolution_id == policy_resolution_id)
            .order_by(self.model.created_at.desc())
            .first()
        )


class EvidenceCollectionJobRepository(TenantRepository[EvidenceCollectionJob]):
    model = EvidenceCollectionJob

    def latest_for_resolution(
        self, organization_id: str, policy_resolution_id: str
    ) -> Optional[EvidenceCollectionJob]:
        return (
            self._scoped(organization_id)
            .filter(self.model.policy_resolution_id == policy_resolution_id)
            .order_by(self.model.created_at.desc())
            .first()
        )


class RawEvidenceRepository(TenantRepository[RawEvidence]):
    model = RawEvidence

    def list_for_job(
        self,
        organization_id: str,
        collection_job_id: str,
        *,
        skip: int = 0,
        limit: int = 500,
    ) -> Sequence[RawEvidence]:
        return (
            self._scoped(organization_id)
            .filter(self.model.collection_job_id == collection_job_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )


class EvidenceValidationResultRepository(
    TenantRepository[EvidenceValidationResult]
):
    model = EvidenceValidationResult

    def list_for_job(
        self,
        organization_id: str,
        collection_job_id: str,
        *,
        skip: int = 0,
        limit: int = 500,
    ) -> Sequence[EvidenceValidationResult]:
        return (
            self._scoped(organization_id)
            .filter(self.model.collection_job_id == collection_job_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def get_for_raw_evidence(
        self, organization_id: str, raw_evidence_id: str
    ) -> Optional[EvidenceValidationResult]:
        return self.find_one(organization_id, raw_evidence_id=raw_evidence_id)


class NormalizedEvidenceRepository(TenantRepository[NormalizedEvidence]):
    model = NormalizedEvidence

    def list_for_job(
        self,
        organization_id: str,
        collection_job_id: str,
        *,
        skip: int = 0,
        limit: int = 500,
    ) -> Sequence[NormalizedEvidence]:
        return (
            self._scoped(organization_id)
            .filter(self.model.collection_job_id == collection_job_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )


class CanonicalEvidencePackageRepository(
    TenantRepository[CanonicalEvidencePackage]
):
    model = CanonicalEvidencePackage

    def latest_for_evaluation(
        self, organization_id: str, evaluation_id: str
    ) -> Optional[CanonicalEvidencePackage]:
        return (
            self._scoped(organization_id)
            .filter(self.model.evaluation_id == evaluation_id)
            .order_by(self.model.created_at.desc())
            .first()
        )

    def list_for_evaluation(
        self, organization_id: str, evaluation_id: str
    ) -> Sequence[CanonicalEvidencePackage]:
        return (
            self._scoped(organization_id)
            .filter(self.model.evaluation_id == evaluation_id)
            .order_by(self.model.created_at.asc())
            .all()
        )


# --------------------------------------------------------------------------- #
# Evidence Sufficiency / Control Evaluation / Assessment repositories
# --------------------------------------------------------------------------- #
class EvidenceSufficiencyRepository(TenantRepository[EvidenceSufficiency]):
    model = EvidenceSufficiency

    def latest_for_resolution(
        self, organization_id: str, policy_resolution_id: str
    ) -> Optional[EvidenceSufficiency]:
        return (
            self._scoped(organization_id)
            .filter(self.model.policy_resolution_id == policy_resolution_id)
            .order_by(self.model.created_at.desc())
            .first()
        )

    def list_for_resolution(
        self,
        organization_id: str,
        policy_resolution_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[EvidenceSufficiency]:
        return (
            self._scoped(organization_id)
            .filter(self.model.policy_resolution_id == policy_resolution_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )


class ControlEvaluationRepository(TenantRepository[ControlEvaluation]):
    model = ControlEvaluation

    def list_for_resolution(
        self,
        organization_id: str,
        policy_resolution_id: str,
        *,
        skip: int = 0,
        limit: int = 500,
    ) -> Sequence[ControlEvaluation]:
        return (
            self._scoped(organization_id)
            .filter(self.model.policy_resolution_id == policy_resolution_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_for_sufficiency(
        self,
        organization_id: str,
        evidence_sufficiency_id: str,
        *,
        skip: int = 0,
        limit: int = 500,
    ) -> Sequence[ControlEvaluation]:
        return (
            self._scoped(organization_id)
            .filter(self.model.evidence_sufficiency_id == evidence_sufficiency_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )


class AssessmentRepository(TenantRepository[Assessment]):
    model = Assessment

    def latest_for_resolution(
        self, organization_id: str, policy_resolution_id: str
    ) -> Optional[Assessment]:
        return (
            self._scoped(organization_id)
            .filter(self.model.policy_resolution_id == policy_resolution_id)
            .order_by(self.model.created_at.desc())
            .first()
        )

    def list_for_resolution(
        self,
        organization_id: str,
        policy_resolution_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Assessment]:
        return (
            self._scoped(organization_id)
            .filter(self.model.policy_resolution_id == policy_resolution_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )


# --------------------------------------------------------------------------- #
# Finding / Remediation branch repositories
# --------------------------------------------------------------------------- #
class FindingRepository(TenantRepository[Finding]):
    model = Finding

    def list_filtered(
        self,
        organization_id: str,
        *,
        status: Optional[str] = None,
        finding_type: Optional[str] = None,
        decision_id: Optional[str] = None,
        intent_id: Optional[str] = None,
        owner: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[Finding]:
        query = self._scoped(organization_id)
        if status is not None:
            query = query.filter(self.model.status == status)
        if finding_type is not None:
            query = query.filter(self.model.finding_type == finding_type)
        if decision_id is not None:
            query = query.filter(self.model.decision_id == decision_id)
        if intent_id is not None:
            query = query.filter(self.model.intent_id == intent_id)
        if owner is not None:
            query = query.filter(self.model.owner == owner)
        return (
            query.order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_for_decision(
        self, organization_id: str, decision_id: str
    ) -> Sequence[Finding]:
        return (
            self._scoped(organization_id)
            .filter(self.model.decision_id == decision_id)
            .order_by(self.model.created_at.asc())
            .all()
        )

    def get_by_finding_id(
        self, organization_id: str, finding_id: str
    ) -> Optional[Finding]:
        return self.find_one(organization_id, finding_id=finding_id)


class RemediationPlanRepository(TenantRepository[RemediationPlan]):
    model = RemediationPlan

    def list_for_finding(
        self, organization_id: str, finding_id: str
    ) -> Sequence[RemediationPlan]:
        return (
            self._scoped(organization_id)
            .filter(self.model.finding_id == finding_id)
            .order_by(self.model.created_at.asc())
            .all()
        )

    def latest_for_finding(
        self, organization_id: str, finding_id: str
    ) -> Optional[RemediationPlan]:
        return (
            self._scoped(organization_id)
            .filter(self.model.finding_id == finding_id)
            .order_by(self.model.created_at.desc())
            .first()
        )


class ResolutionEvidenceRepository(TenantRepository[ResolutionEvidence]):
    model = ResolutionEvidence

    def list_for_finding(
        self, organization_id: str, finding_id: str
    ) -> Sequence[ResolutionEvidence]:
        return (
            self._scoped(organization_id)
            .filter(self.model.finding_id == finding_id)
            .order_by(self.model.created_at.asc())
            .all()
        )


class DevSyncDispatchRepository(TenantRepository[DevSyncDispatch]):
    model = DevSyncDispatch

    def get_by_callback_reference(
        self, organization_id: str, callback_reference: str
    ) -> Optional[DevSyncDispatch]:
        return self.find_one(
            organization_id, callback_reference=callback_reference
        )

    def list_for_finding(
        self, organization_id: str, finding_id: str
    ) -> Sequence[DevSyncDispatch]:
        return (
            self._scoped(organization_id)
            .filter(self.model.finding_id == finding_id)
            .order_by(self.model.created_at.asc())
            .all()
        )


class ReviewRecordRepository(TenantRepository[ReviewRecord]):
    model = ReviewRecord

    def list_for_finding(
        self, organization_id: str, finding_id: str
    ) -> Sequence[ReviewRecord]:
        return (
            self._scoped(organization_id)
            .filter(self.model.finding_id == finding_id)
            .order_by(self.model.created_at.asc())
            .all()
        )


# --------------------------------------------------------------------------- #
# Integration / event-feed repositories (ProofSync / AuditSync / RegSync)
# --------------------------------------------------------------------------- #
class IntegrationEventRepository(TenantRepository[IntegrationEvent]):
    model = IntegrationEvent

    def get_by_event_id(
        self, organization_id: str, event_id: str
    ) -> Optional[IntegrationEvent]:
        """Return the outbox event for a deterministic ``event_id``, if any."""
        return self.find_one(organization_id, event_id=event_id)

    def list_for_aggregate(
        self,
        organization_id: str,
        aggregate_type: str,
        aggregate_id: str,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[IntegrationEvent]:
        return (
            self._scoped(organization_id)
            .filter(self.model.aggregate_type == aggregate_type)
            .filter(self.model.aggregate_id == aggregate_id)
            .order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )


class EventDeliveryRepository(TenantRepository[EventDelivery]):
    model = EventDelivery

    def list_for_event(
        self, organization_id: str, event_id: str
    ) -> Sequence[EventDelivery]:
        return (
            self._scoped(organization_id)
            .filter(self.model.event_id == event_id)
            .order_by(self.model.created_at.asc())
            .all()
        )

    def list_for_channel(
        self,
        organization_id: str,
        channel: str,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[EventDelivery]:
        query = self._scoped(organization_id).filter(
            self.model.channel == channel
        )
        if status is not None:
            query = query.filter(self.model.status == status)
        return (
            query.order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def list_deliverable(
        self,
        organization_id: str,
        *,
        channel: Optional[str] = None,
        limit: int = 100,
    ) -> list[EventDelivery]:
        """Return the deliveries eligible for dispatch, for the tenant.

        A delivery is *deliverable* when it is:

        * ``PENDING``, or
        * ``FAILED`` and still retryable — i.e. it has not exhausted its
          attempt budget (``attempts < max_attempts``) and its back-off gate has
          elapsed (``next_retry_at`` is ``None`` or in the past).

        The following are never returned: ``DELIVERED`` rows, ``DEAD_LETTER``
        rows, rows at/above the maximum-attempt threshold, and retryable rows
        whose ``next_retry_at`` is still in the future.

        This is a **read-only** query: it never mutates delivery status (status
        transitions belong to the dispatch/service layer). Results are ordered
        deterministically by ``next_retry_at`` (nulls first), then
        ``created_at``, then ``id``, and the method always returns a list (an
        empty list when nothing is deliverable) — never ``None``.
        """
        from app.utils.canonical_enums import EventDeliveryStatus
        from app.utils.timestamps import ensure_aware, utc_now

        query = self._scoped(organization_id).filter(
            self.model.status.in_(
                [
                    EventDeliveryStatus.PENDING.value,
                    EventDeliveryStatus.FAILED.value,
                ]
            ),
            # Exclude rows that have exhausted their attempt budget. Column vs.
            # column comparison is timezone-agnostic and portable.
            self.model.attempts < self.model.max_attempts,
        )
        if channel is not None:
            query = query.filter(self.model.channel == channel)

        # Deterministic ordering: next_retry_at asc (nulls first so freshly
        # pending rows lead), then created_at asc, then a stable id tie-break.
        candidates = query.order_by(
            self.model.next_retry_at.asc(),
            self.model.created_at.asc(),
            self.model.id.asc(),
        ).all()

        # The back-off gate is evaluated in Python with timezone-safe
        # comparisons so naive timestamps persisted by some backends (e.g.
        # SQLite) never compare incorrectly against an aware "now".
        now = utc_now()
        deliverable: list[EventDelivery] = []
        for delivery in candidates:
            if delivery.status == EventDeliveryStatus.FAILED.value:
                retry_at = ensure_aware(delivery.next_retry_at)
                if retry_at is not None and retry_at > now:
                    continue
            deliverable.append(delivery)
            if len(deliverable) >= limit:
                break
        return deliverable


class CanonicalAIProofRepository(TenantRepository[CanonicalAIProof]):
    model = CanonicalAIProof

    def get_by_hash(
        self, organization_id: str, aiproof_hash: str
    ) -> Optional[CanonicalAIProof]:
        return self.find_one(organization_id, aiproof_hash=aiproof_hash)

    def list_by(
        self,
        organization_id: str,
        *,
        intent_id: Optional[str] = None,
        actor_identity_id: Optional[str] = None,
        governance_evaluation_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[CanonicalAIProof]:
        """List proofs in the tenant filtered by optional lifecycle references."""
        query = self._scoped(organization_id)
        if intent_id is not None:
            query = query.filter(self.model.intent_id == intent_id)
        if actor_identity_id is not None:
            query = query.filter(self.model.actor_identity_id == actor_identity_id)
        if governance_evaluation_id is not None:
            query = query.filter(
                self.model.governance_evaluation_id == governance_evaluation_id
            )
        if correlation_id is not None:
            query = query.filter(self.model.correlation_id == correlation_id)
        return (
            query.order_by(self.model.created_at.asc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def current_for_intent(
        self, organization_id: str, intent_id: str
    ) -> Optional[CanonicalAIProof]:
        """Return the newest non-superseded proof for an intent, if any."""
        return (
            self._scoped(organization_id)
            .filter(self.model.intent_id == intent_id)
            .filter(self.model.superseded_by_aiproof_id.is_(None))
            .order_by(self.model.created_at.desc())
            .first()
        )


# --------------------------------------------------------------------------- #
# Continuous monitoring & automated re-evaluation repositories
# --------------------------------------------------------------------------- #
class MonitoringEventRepository(TenantRepository[MonitoringEvent]):
    model = MonitoringEvent

    def get_by_event_uid(
        self, organization_id: str, event_uid: str
    ) -> Optional[MonitoringEvent]:
        return self.find_one(organization_id, event_uid=event_uid)

    def list_filtered(
        self,
        organization_id: str,
        *,
        change_type: Optional[str] = None,
        affected_object_type: Optional[str] = None,
        affected_object_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[MonitoringEvent]:
        query = self._scoped(organization_id)
        if change_type is not None:
            query = query.filter(self.model.change_type == change_type)
        if affected_object_type is not None:
            query = query.filter(
                self.model.affected_object_type == affected_object_type
            )
        if affected_object_id is not None:
            query = query.filter(
                self.model.affected_object_id == affected_object_id
            )
        if correlation_id is not None:
            query = query.filter(self.model.correlation_id == correlation_id)
        return (
            query.order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )


class ReevaluationRunRepository(TenantRepository[ReevaluationRun]):
    model = ReevaluationRun

    def list_for_event(
        self, organization_id: str, monitoring_event_id: str
    ) -> Sequence[ReevaluationRun]:
        return (
            self._scoped(organization_id)
            .filter(self.model.monitoring_event_id == monitoring_event_id)
            .order_by(self.model.created_at.asc())
            .all()
        )

    def list_filtered(
        self,
        organization_id: str,
        *,
        status: Optional[str] = None,
        intent_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> Sequence[ReevaluationRun]:
        query = self._scoped(organization_id)
        if status is not None:
            query = query.filter(self.model.status == status)
        if intent_id is not None:
            query = query.filter(self.model.intent_id == intent_id)
        return (
            query.order_by(self.model.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
