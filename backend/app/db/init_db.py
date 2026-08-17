"""Database initialisation — create all tables."""

from app.core.database import Base, engine

# Import every model so SQLAlchemy registers them on Base.metadata
from app.models.agent import Agent  # noqa: F401
from app.models.policy import Policy  # noqa: F401
from app.models.transaction import Transaction  # noqa: F401
from app.models.approval import Approval  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.proof_bundle import ProofBundle  # noqa: F401  (deprecated)
from app.models.aiproof import AIProof  # noqa: F401  (legacy x402 proof bundle)
from app.models.canonical_aiproof import CanonicalAIProof  # noqa: F401  (canonical proof)

# Tenant registry — the real, validated organization boundary.
from app.models.organization import Organization  # noqa: F401

# Canonical first-class runtime domain objects.
from app.models.actor_identity import ActorIdentity  # noqa: F401
from app.models.intent import Intent  # noqa: F401
from app.models.target import Target  # noqa: F401
from app.models.operational_context import OperationalContext  # noqa: F401
from app.models.governance_evaluation import GovernanceEvaluation  # noqa: F401
from app.models.decision import Decision  # noqa: F401
from app.models.execution_authorization import ExecutionAuthorization  # noqa: F401
from app.models.external_execution_result import ExternalExecutionResult  # noqa: F401
from app.models.governance_package import ExecutableGovernancePackage  # noqa: F401
from app.models.policy_resolution import PolicyResolution  # noqa: F401
from app.models.applicability_evaluation import ApplicabilityEvaluation  # noqa: F401
from app.models.applicable_control_set import ApplicableControlSet  # noqa: F401
from app.models.evidence_requirement_set import EvidenceRequirementSet  # noqa: F401

# Evidence layer (collection, validation, normalization, packaging).
from app.models.evidence_source import EvidenceSource  # noqa: F401
from app.models.evidence_orchestration_plan import (  # noqa: F401
    EvidenceOrchestrationPlan,
)
from app.models.evidence_collection_job import EvidenceCollectionJob  # noqa: F401
from app.models.raw_evidence import RawEvidence  # noqa: F401
from app.models.evidence_validation_result import (  # noqa: F401
    EvidenceValidationResult,
)
from app.models.normalized_evidence import NormalizedEvidence  # noqa: F401
from app.models.canonical_evidence_package import (  # noqa: F401
    CanonicalEvidencePackage,
)

# Evidence Sufficiency, Control Evaluation and Assessment stages.
from app.models.evidence_sufficiency import EvidenceSufficiency  # noqa: F401
from app.models.control_evaluation import ControlEvaluation  # noqa: F401
from app.models.assessment import Assessment  # noqa: F401

# Finding and remediation branch.
from app.models.finding import Finding  # noqa: F401
from app.models.remediation_plan import RemediationPlan  # noqa: F401
from app.models.resolution_evidence import ResolutionEvidence  # noqa: F401
from app.models.devsync_dispatch import DevSyncDispatch  # noqa: F401
from app.models.review_record import ReviewRecord  # noqa: F401

# Integration / event-feed outbox (ProofSync / AuditSync / RegSync).
from app.models.integration_event import IntegrationEvent  # noqa: F401
from app.models.event_delivery import EventDelivery  # noqa: F401

# Continuous monitoring & automated re-evaluation.
from app.models.monitoring_event import MonitoringEvent  # noqa: F401
from app.models.reevaluation_run import ReevaluationRun  # noqa: F401


def init_db() -> None:
    """Create database tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)
