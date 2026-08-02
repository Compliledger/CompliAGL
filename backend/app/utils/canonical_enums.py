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
