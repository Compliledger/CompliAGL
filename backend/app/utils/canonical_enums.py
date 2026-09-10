"""Canonical enumerations for the first-class runtime domain objects.

These enums back the canonical runtime sequence:

    Actor Identity -> Intent -> Target -> Operational Context ->
    Governance Evaluation -> Decision -> Execution Authorization ->
    External Execution Result -> AIProof

They are kept separate from the legacy :mod:`app.utils.enums` so the canonical
domain has a single, unambiguous vocabulary without disturbing existing code.
"""

from __future__ import annotations

from enum import Enum


class CanonicalActorType(str, Enum):
    """High-level classification of an actor identity.

    The identity model is *pluggable* — credential type (below) captures the
    concrete identity technology (DID, VC, Hedera account, OAuth/OIDC, ...).
    """

    AI_AGENT = "AI_AGENT"
    HUMAN = "HUMAN"
    SERVICE = "SERVICE"
    ORGANIZATION = "ORGANIZATION"
    AUTONOMOUS_SERVICE = "AUTONOMOUS_SERVICE"
    DEVICE = "DEVICE"
    WORKFLOW = "WORKFLOW"


class CredentialType(str, Enum):
    """Pluggable identity credential technology.

    A DID or VC is **not** required for every actor. ``NONE`` allows an actor
    identity with only internal/enterprise identifiers.
    """

    NONE = "NONE"
    DID = "DID"
    VC = "VC"
    HEDERA_ACCOUNT = "HEDERA_ACCOUNT"
    HEDERA_AGENT_ACCOUNT = "HEDERA_AGENT_ACCOUNT"
    OAUTH_OIDC = "OAUTH_OIDC"
    ENTERPRISE_SERVICE = "ENTERPRISE_SERVICE"


class VerificationStatus(str, Enum):
    """Verification status of an actor identity's credential."""

    UNVERIFIED = "UNVERIFIED"
    PENDING = "PENDING"
    VERIFIED = "VERIFIED"
    FAILED = "FAILED"
    REVOKED = "REVOKED"


class RevocationStatus(str, Enum):
    """Revocation status of an actor identity."""

    ACTIVE = "ACTIVE"
    REVOKED = "REVOKED"


class IntentType(str, Enum):
    """Coarse classification of an intent."""

    PAYMENT = "PAYMENT"
    TRANSFER = "TRANSFER"
    API_CALL = "API_CALL"
    DATA_ACCESS = "DATA_ACCESS"
    MODEL_INVOCATION = "MODEL_INVOCATION"
    WORKFLOW_ACTION = "WORKFLOW_ACTION"
    CUSTOM = "CUSTOM"


class IntentStatus(str, Enum):
    """Lifecycle status of an intent."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    EVALUATED = "EVALUATED"
    AUTHORIZED = "AUTHORIZED"
    EXECUTED = "EXECUTED"
    DENIED = "DENIED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class TargetType(str, Enum):
    """Universal target types an intent can act upon."""

    ACTOR = "ACTOR"
    ASSET = "ASSET"
    TRANSACTION = "TRANSACTION"
    SYSTEM = "SYSTEM"
    MODEL = "MODEL"
    DEVICE = "DEVICE"
    PROCESS = "PROCESS"
    DATASET = "DATASET"
    MERCHANT = "MERCHANT"
    API = "API"
    SMART_CONTRACT = "SMART_CONTRACT"
    ACCOUNT = "ACCOUNT"
    WORKFLOW = "WORKFLOW"
    CUSTOM = "CUSTOM"


class TrustStatus(str, Enum):
    """Trust posture assigned to a target."""

    UNKNOWN = "UNKNOWN"
    UNTRUSTED = "UNTRUSTED"
    TRUSTED = "TRUSTED"
    BLOCKED = "BLOCKED"


class EnvironmentType(str, Enum):
    """Operational environment of a context."""

    PRODUCTION = "PRODUCTION"
    STAGING = "STAGING"
    DEVELOPMENT = "DEVELOPMENT"
    TEST = "TEST"
    SANDBOX = "SANDBOX"


class EvaluationStatus(str, Enum):
    """Lifecycle status of a governance evaluation."""

    PENDING = "PENDING"
    EVALUATED = "EVALUATED"
    FAILED = "FAILED"


class DecisionOutcome(str, Enum):
    """Canonical deterministic decision outcome."""

    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"


class AuthorizationStatus(str, Enum):
    """Lifecycle status of an execution authorization.

    The canonical signed-authorization lifecycle is
    ``ISSUED -> ACTIVE -> CONSUMED`` with ``REVOKED`` / ``EXPIRED`` as terminal
    exits. ``PENDING`` / ``AUTHORIZED`` are retained for backward compatibility
    with the earlier lightweight authorization flow.
    """

    # Canonical signed-authorization states.
    ISSUED = "ISSUED"
    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"

    # Legacy states (retained for backward compatibility).
    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"


class DecisionSupersessionStatus(str, Enum):
    """Whether a decision is the current verdict or has been superseded.

    Decisions are immutable. A re-evaluation never mutates an existing decision;
    it creates a **new** :class:`Decision` object and marks the prior decision as
    ``SUPERSEDED``.
    """

    CURRENT = "CURRENT"
    SUPERSEDED = "SUPERSEDED"


class ExecutionResultStatus(str, Enum):
    """Lifecycle status of an external execution result."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"


# --------------------------------------------------------------------------- #
# Executable governance package vocabulary
# --------------------------------------------------------------------------- #
class PackageStatus(str, Enum):
    """Lifecycle status of an executable governance package.

    Packages are authored by CompliLedger, validated and approved, then
    published to CompliAGL as immutable, versioned, executable governance.
    """

    DRAFT = "DRAFT"
    VALIDATED = "VALIDATED"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"
    SUPERSEDED = "SUPERSEDED"
    RETIRED = "RETIRED"
    REJECTED = "REJECTED"


class PolicyResolutionStatus(str, Enum):
    """Lifecycle status of a policy-resolution record.

    Policy Resolution is a deterministic runtime stage that runs *before* the
    decision engine. It selects the governing package versions for a concrete
    (actor, intent, target, context) tuple.
    """

    RESOLVED = "RESOLVED"
    NO_APPLICABLE_POLICY = "NO_APPLICABLE_POLICY"
    CONFLICT_RESOLVED = "CONFLICT_RESOLVED"


class ApplicabilityResult(str, Enum):
    """Deterministic outcome of evaluating a single requirement's applicability.

    ``INDETERMINATE`` is a first-class result: it is never silently collapsed to
    ``NOT_APPLICABLE``. Missing context that prevents a deterministic decision
    surfaces as ``INDETERMINATE`` so it cannot silently produce approval.
    """

    APPLICABLE = "APPLICABLE"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    CONDITIONAL = "CONDITIONAL"
    INDETERMINATE = "INDETERMINATE"


class ControlDeterminationStatus(str, Enum):
    """Status carried by a control selected during Control Determination.

    Control Determination runs **after** Applicability Evaluation and
    **before** the decision engine. It selects the controls mapped to
    ``APPLICABLE`` or conditionally applicable requirements and *preserves* the
    ``CONDITIONAL`` and ``INDETERMINATE`` states rather than collapsing them.

    A control whose requirements are all ``NOT_APPLICABLE`` is excluded and so
    never carries this status. ``INDETERMINATE`` includes the case where the
    applicability basis for a control is missing — it is never silently treated
    as ``NOT_APPLICABLE``.
    """

    APPLICABLE = "APPLICABLE"
    CONDITIONAL = "CONDITIONAL"
    INDETERMINATE = "INDETERMINATE"


class RequiredEvidenceState(str, Enum):
    """Deterministic state of an evidence requirement after resolution.

    ``UNRESOLVED`` is a first-class state: when the applicability basis for the
    controls that need an evidence item is missing or indeterminate, the item is
    ``UNRESOLVED`` rather than silently ``NOT_REQUIRED`` — missing basis can
    never silently produce success downstream.
    """

    REQUIRED = "REQUIRED"
    OPTIONAL = "OPTIONAL"
    CONDITIONAL = "CONDITIONAL"
    NOT_REQUIRED = "NOT_REQUIRED"
    UNRESOLVED = "UNRESOLVED"


class EvidenceSourceType(str, Enum):
    """Generic classification of an authoritative evidence source.

    These are deliberately platform-neutral. CompliAGL never hardcodes a domain
    (airline, payment app, ...). A concrete deployment maps its real systems onto
    these generic source types via connectors.

    * ``GOVERNANCE_REGISTRY`` — the CompliLedger governance-package registry.
    * ``IDENTITY_PROVIDER`` — an internal identity / delegation authority.
    * ``EXTERNAL_APPLICATION`` — an external merchant or application API.
    * ``ACCOUNT_STATE`` — a wallet / account / allowance source.
    * ``APPROVAL_WORKFLOW`` — an approval source.
    * ``EXECUTION_RESULT`` — an external execution-result source.
    """

    GOVERNANCE_REGISTRY = "GOVERNANCE_REGISTRY"
    IDENTITY_PROVIDER = "IDENTITY_PROVIDER"
    EXTERNAL_APPLICATION = "EXTERNAL_APPLICATION"
    ACCOUNT_STATE = "ACCOUNT_STATE"
    APPROVAL_WORKFLOW = "APPROVAL_WORKFLOW"
    EXECUTION_RESULT = "EXECUTION_RESULT"


class EvidenceCollectionStatus(str, Enum):
    """Status of a single evidence collection attempt or an aggregate job.

    ``UNRESOLVED`` is first-class: when no authoritative connector can serve a
    requirement it is marked ``UNRESOLVED`` rather than silently succeeding.
    Evidence is never fabricated, so an absent item is always explicit.
    """

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COLLECTED = "COLLECTED"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    UNRESOLVED = "UNRESOLVED"
    NOT_FOUND = "NOT_FOUND"
    REJECTED_MOCK = "REJECTED_MOCK"
    # Aggregate job states.
    PARTIAL = "PARTIAL"
    COMPLETED = "COMPLETED"


class EvidenceValidationOutcome(str, Enum):
    """Deterministic outcome of validating a raw evidence item.

    ``INDETERMINATE`` is first-class: a check that cannot be evaluated never
    silently becomes ``VALID``.
    """

    VALID = "VALID"
    INVALID = "INVALID"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    STALE = "STALE"
    UNTRUSTED_SOURCE = "UNTRUSTED_SOURCE"
    SUBJECT_MISMATCH = "SUBJECT_MISMATCH"
    TARGET_MISMATCH = "TARGET_MISMATCH"
    INDETERMINATE = "INDETERMINATE"


class SensitivityClassification(str, Enum):
    """Sensitivity classification of an evidence payload.

    Payloads classified ``PII``, ``SENSITIVE`` or ``SECRET`` must never be copied
    into public proof or blockchain projections — only their hashes are.
    """

    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    PII = "PII"
    SENSITIVE = "SENSITIVE"
    SECRET = "SECRET"


class ConnectorHealthStatus(str, Enum):
    """Health posture reported by an evidence connector."""

    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    UNAVAILABLE = "UNAVAILABLE"


class ExpressionOperator(str, Enum):
    """The closed set of operators the deterministic expression engine allows.

    No other operator may be used. The engine never evaluates arbitrary code
    (``eval``/``exec`` are never used); only these named, side-effect-free
    operators are supported.
    """

    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    IN = "in"
    NOT_IN = "not_in"
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    EXISTS = "exists"
    NOT_EXISTS = "not_exists"
    CONTAINS = "contains"
    STARTS_WITH = "starts_with"
    DATE_BEFORE = "date_before"
    DATE_AFTER = "date_after"
    ALL = "all"
    ANY = "any"
    NOT = "not"


class RequirementClassification(str, Enum):
    """Deontic classification of a requirement."""

    OBLIGATION = "OBLIGATION"
    PROHIBITION = "PROHIBITION"
    PERMISSION = "PERMISSION"


class ControlFailureDisposition(str, Enum):
    """What a failed control does to a runtime decision."""

    DENY = "DENY"
    ESCALATE = "ESCALATE"
    FLAG = "FLAG"
    ALLOW_WITH_REMEDIATION = "ALLOW_WITH_REMEDIATION"


class GovernanceSeverity(str, Enum):
    """Severity classification shared by requirements and controls."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


# --------------------------------------------------------------------------- #
# Evidence Sufficiency, Control Evaluation and Assessment vocabulary
# --------------------------------------------------------------------------- #
class EvidenceRequirementSufficiency(str, Enum):
    """Deterministic sufficiency verdict for a single evidence requirement.

    Produced by the Evidence Sufficiency stage when the Canonical Evidence
    Package is evaluated against the EvidenceRequirementSet. ``SATISFIED``
    requires enough valid normalized evidence to meet the requirement's
    cardinality; the remaining states are all first-class and are never
    silently collapsed into ``SATISFIED``.
    """

    SATISFIED = "SATISFIED"
    PARTIAL = "PARTIAL"
    MISSING = "MISSING"
    INVALID = "INVALID"
    STALE = "STALE"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class EvidenceSufficiencyOutcome(str, Enum):
    """Overall deterministic outcome of the Evidence Sufficiency stage.

    ``SUFFICIENT`` is *never* produced when any mandatory evidence requirement
    is missing, invalid, stale, expired, revoked or not evaluable.
    """

    SUFFICIENT = "SUFFICIENT"
    PARTIAL = "PARTIAL"
    INSUFFICIENT = "INSUFFICIENT"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class ControlEvaluationOutcome(str, Enum):
    """Deterministic outcome of formally evaluating a single control.

    A control is evaluated against **normalized evidence only**, using the
    approved deterministic expression engine and the exact control + governance
    package versions. Raw intent assertions can never satisfy a control without
    normalized validated evidence.
    """

    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


class AssessmentOutcome(str, Enum):
    """Deterministic outcome of aggregating control evaluations.

    Assessment is **factual**: it aggregates the control evaluations without
    producing the final business decision. Mapping an assessment into
    ``APPROVED`` / ``DENIED`` / ``ESCALATED`` is the separate Decision stage.
    """

    SATISFIED = "SATISFIED"
    NOT_SATISFIED = "NOT_SATISFIED"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"


# --------------------------------------------------------------------------- #
# Finding, Remediation, Resolution and DevSync vocabulary
# --------------------------------------------------------------------------- #
class FindingType(str, Enum):
    """Classification of why a governance finding was raised.

    A **Finding** is a first-class, persistent record created when an assessment
    or decision is not satisfied / not evaluable / requires manual review /
    denied / escalated (subject to governance-package configuration).
    """

    CONTROL_FAILURE = "CONTROL_FAILURE"
    EVIDENCE_GAP = "EVIDENCE_GAP"
    INVALID_EVIDENCE = "INVALID_EVIDENCE"
    POLICY_PROHIBITION = "POLICY_PROHIBITION"
    MANUAL_REVIEW = "MANUAL_REVIEW"
    OPERATIONAL_STATE_CONFLICT = "OPERATIONAL_STATE_CONFLICT"
    AUTHORITY_FAILURE = "AUTHORITY_FAILURE"
    # A governance policy *condition* escalated an otherwise-clean decision
    # (assessment SATISFIED, no failing control). The only resolution is an
    # authority-verified human approval — never remediation evidence, a plain
    # review record, or re-assessment. Given its own type so the
    # remediation/re-assessment path can structurally refuse it (see
    # finding_service._escalation_approval_required, resolution_validation_service,
    # reassessment_service).
    ESCALATION_APPROVAL_REQUIRED = "ESCALATION_APPROVAL_REQUIRED"
    OTHER = "OTHER"


class FindingStatus(str, Enum):
    """Lifecycle status of a finding.

    ``RESOLVED_PENDING_VALIDATION`` is deliberately distinct from ``CLOSED``:
    marking remediation complete is *not* proof of resolution. A finding only
    reaches ``CLOSED`` after validated resolution evidence and a new deterministic
    decision. ``TERMINATED`` is the terminal state for a non-remediable finding.
    """

    OPEN = "OPEN"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    RESOLVED_PENDING_VALIDATION = "RESOLVED_PENDING_VALIDATION"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CLOSED = "CLOSED"
    ACCEPTED_RISK = "ACCEPTED_RISK"
    TERMINATED = "TERMINATED"


class FindingDecisionImpact(str, Enum):
    """The effect the finding's underlying condition had on the decision."""

    DENIED = "DENIED"
    ESCALATED = "ESCALATED"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
    NOT_EVALUABLE = "NOT_EVALUABLE"
    ADVISORY = "ADVISORY"


class RemediationEligibility(str, Enum):
    """Whether a finding may be remediated at all.

    Not every denial is remediable. A terminal policy prohibition is
    ``INELIGIBLE`` and can never be resolved into an authorization.
    """

    ELIGIBLE = "ELIGIBLE"
    CONDITIONAL = "CONDITIONAL"
    INELIGIBLE = "INELIGIBLE"


class RemediationPlanStatus(str, Enum):
    """Lifecycle status of a remediation plan."""

    DRAFT = "DRAFT"
    OPEN = "OPEN"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    DISPATCHED = "DISPATCHED"
    REMEDIATION_COMPLETE = "REMEDIATION_COMPLETE"
    VALIDATED = "VALIDATED"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    CANCELLED = "CANCELLED"


class RemediationPriority(str, Enum):
    """Priority of a remediation plan."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


class ResolutionValidationOutcome(str, Enum):
    """Deterministic outcome of validating a finding's resolution.

    ``VALIDATED`` requires sufficient *validated* resolution evidence. It is
    never produced from a mere "remediation complete" signal — marking
    remediation complete is not proof of resolution.
    """

    VALIDATED = "VALIDATED"
    REJECTED = "REJECTED"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NOT_EVALUABLE = "NOT_EVALUABLE"


class DevSyncDispatchStatus(str, Enum):
    """Outbound dispatch status of a DevSync payload.

    DevSync is an *integration surface*, never the source of truth for
    governance. CompliAGL retains the canonical finding and remediation state.
    """

    PENDING = "PENDING"
    DISPATCHED = "DISPATCHED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    FAILED = "FAILED"


class DevSyncCallbackStatus(str, Enum):
    """Inbound status a DevSync system reports for a dispatched finding."""

    RECEIVED = "RECEIVED"
    IN_PROGRESS = "IN_PROGRESS"
    BLOCKED = "BLOCKED"
    COMPLETED = "COMPLETED"
    REJECTED = "REJECTED"


class ReviewType(str, Enum):
    """Kind of human review that produced a review record."""

    MANUAL_REVIEW = "MANUAL_REVIEW"
    ESCALATION_APPROVAL = "ESCALATION_APPROVAL"


class ReviewOutcome(str, Enum):
    """Outcome recorded by a human reviewer."""

    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    NEEDS_MORE_INFO = "NEEDS_MORE_INFO"


class EscalationApprovalStatus(str, Enum):
    """Lifecycle of an :class:`EscalationApproval`.

    An escalation approval authorises re-evaluation of an ``ESCALATED`` decision
    that escalated for human approval. It is time-bounded (``valid_until``) and
    consumed by exactly one re-decision.

    * ``ACTIVE`` — granted and not yet consumed. Whether it is still *within* its
      validity window is evaluated at decision time against ``valid_until`` (see
      ``runtime_facts.build_approval_facts``), not stored here.
    * ``CONSUMED`` — a re-decision used this approval to upgrade the escalation;
      ``consumed_by_decision_id`` points at the new decision.
    * ``EXPIRED`` — explicitly retired after its window passed without being
      consumed (a terminal, non-reusable state).
    """

    ACTIVE = "ACTIVE"
    CONSUMED = "CONSUMED"
    EXPIRED = "EXPIRED"


# --------------------------------------------------------------------------- #
# Integration / event-feed vocabulary (ProofSync / AuditSync / RegSync)
# --------------------------------------------------------------------------- #
class IntegrationEventType(str, Enum):
    """Canonical governance/assurance events published to the sync portals.

    CompliAGL / CompliLedger remains the canonical proof source. These events are
    the *only* contract the ProofSync, AuditSync and RegSync portals consume —
    they carry references and authorized projections, never a portal-owned copy
    of the canonical proof store.
    """

    ASSESSMENT_CREATED = "assessment.created"
    DECISION_CREATED = "decision.created"
    FINDING_CREATED = "finding.created"
    REMEDIATION_UPDATED = "remediation.updated"
    RESOLUTION_VALIDATED = "resolution.validated"
    PROOF_GENERATED = "proof.generated"
    PROOF_ANCHORED = "proof.anchored"
    PROOF_VERIFIED = "proof.verified"
    PROOF_SUPERSEDED = "proof.superseded"
    MONITORING_CHANGE_DETECTED = "monitoring.change_detected"
    REEVALUATION_COMPLETED = "reevaluation.completed"


class IntegrationChannel(str, Enum):
    """The authorized outbound integration surfaces (sync portals).

    * ``PROOFSYNC`` — client-facing real-time governance and assurance feed.
    * ``AUDITSYNC`` — auditor-authorized evidence-reference and history feed.
    * ``REGSYNC`` — regulator-authorized regulation-scoped supervision feed.
    """

    PROOFSYNC = "PROOFSYNC"
    AUDITSYNC = "AUDITSYNC"
    REGSYNC = "REGSYNC"


class EventDeliveryStatus(str, Enum):
    """Persistent delivery state of a single outbound event delivery.

    Deliveries follow the transactional-outbox lifecycle
    ``PENDING -> DELIVERED`` on success, ``PENDING/FAILED -> FAILED`` (retryable)
    on a transient failure, and ``FAILED -> DEAD_LETTER`` once the maximum number
    of attempts is exhausted.
    """

    PENDING = "PENDING"
    DELIVERED = "DELIVERED"
    FAILED = "FAILED"
    DEAD_LETTER = "DEAD_LETTER"


class SubscriberRole(str, Enum):
    """Authorized subscriber roles for the sync portals.

    Role scoping is enforced at the feed boundary: a caller may only read a
    channel their role is authorized for (see
    :mod:`app.services.canonical.integration.scoping`).
    """

    CLIENT = "CLIENT"
    GOVERNANCE_ADMIN = "GOVERNANCE_ADMIN"
    AUDITOR = "AUDITOR"
    REGULATOR = "REGULATOR"
    COMPLILEDGER_SERVICE = "COMPLILEDGER_SERVICE"


# --------------------------------------------------------------------------- #
# Continuous monitoring & automated re-evaluation vocabulary
# --------------------------------------------------------------------------- #
class MonitoringChangeType(str, Enum):
    """The canonical change categories the continuous monitor observes.

    Each value is a discrete, auditable class of change that can invalidate a
    prior governed outcome and therefore trigger impact analysis and (where
    warranted) an automated re-evaluation.
    """

    POLICY_CHANGED = "POLICY_CHANGED"
    GOVERNANCE_PACKAGE_CHANGED = "GOVERNANCE_PACKAGE_CHANGED"
    OPERATIONAL_CONTEXT_CHANGED = "OPERATIONAL_CONTEXT_CHANGED"
    EVIDENCE_CHANGED = "EVIDENCE_CHANGED"
    EVIDENCE_EXPIRED = "EVIDENCE_EXPIRED"
    EVIDENCE_REVOKED = "EVIDENCE_REVOKED"
    FINDING_STATUS_CHANGED = "FINDING_STATUS_CHANGED"
    REMEDIATION_STATUS_CHANGED = "REMEDIATION_STATUS_CHANGED"
    AUTHORIZATION_EXPIRED = "AUTHORIZATION_EXPIRED"
    AUTHORIZATION_REVOKED = "AUTHORIZATION_REVOKED"
    EXTERNAL_EXECUTION_RESULT_CHANGED = "EXTERNAL_EXECUTION_RESULT_CHANGED"
    TARGET_STATE_CHANGED = "TARGET_STATE_CHANGED"
    ACTOR_AUTHORITY_CHANGED = "ACTOR_AUTHORITY_CHANGED"


class MonitoringSeverity(str, Enum):
    """Severity of a detected monitoring change."""

    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ReevaluationStatus(str, Enum):
    """Lifecycle status of an automated re-evaluation run.

    A run is created ``PENDING``, moves to ``IN_PROGRESS`` while impact analysis
    and record creation happen, and terminates as ``COMPLETED`` (new immutable
    records produced), ``NO_ACTION`` (impact analysis found nothing affected) or
    ``FAILED``.
    """

    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    NO_ACTION = "NO_ACTION"
    FAILED = "FAILED"
