"""Business enums and domain constants for CompliAGL.

These enums define the strongly typed values used across the governance layer
for decision outcomes, transaction lifecycle states, approval workflows,
actor classifications, policy management, risk assessment, and proof records.

Business rule expectations:
- APPROVED means the transaction can proceed immediately.
- DENIED means the transaction is blocked by policy.
- ESCALATED means the transaction requires human or second-wallet approval.
- PENDING_APPROVAL means the transaction is waiting for approval after escalation.
"""

from enum import Enum


class DecisionResult(str, Enum):
    """Outcome of a governance decision evaluation.

    Returned by the Decision Engine after evaluating a transaction
    against all active policy rules.
    """

    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"
    PENDING_APPROVAL = "PENDING_APPROVAL"


class TransactionStatus(str, Enum):
    """Lifecycle status of an agent wallet transaction.

    Tracks the transaction from initial submission through governance
    evaluation to final execution or failure.
    """

    SUBMITTED = "SUBMITTED"
    EVALUATED = "EVALUATED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


class ApprovalStatus(str, Enum):
    """Status of a human approval request.

    Used by the Escalation Engine when a transaction requires
    human or second-wallet review.
    """

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"


class ActorType(str, Enum):
    """Classification of an actor in the governance system.

    Identifies whether a participant is an autonomous agent,
    a human reviewer, or an organization entity.
    """

    AGENT = "AGENT"
    HUMAN = "HUMAN"
    ORGANIZATION = "ORGANIZATION"


class PolicyStatus(str, Enum):
    """Activation status of a governance policy.

    Controls whether a policy is currently enforced by the Policy Engine.
    """

    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


class RiskLevel(str, Enum):
    """Risk classification for transactions or policies.

    Used to determine escalation thresholds and approval requirements.
    """

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class ProofStatus(str, Enum):
    """Status of a cryptographic proof record.

    Tracks the lifecycle of a proof bundle from generation through
    blockchain anchoring.
    """

    GENERATED = "GENERATED"
    ANCHORED = "ANCHORED"
    FAILED = "FAILED"
