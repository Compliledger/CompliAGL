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
    """Lifecycle status of an execution authorization."""

    PENDING = "PENDING"
    AUTHORIZED = "AUTHORIZED"
    CONSUMED = "CONSUMED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


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
