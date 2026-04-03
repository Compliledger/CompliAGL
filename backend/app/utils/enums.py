"""Shared enumerations used across the application."""

from enum import Enum


class DecisionStatus(str, Enum):
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"


class AgentStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    REVOKED = "REVOKED"


class ActorType(str, Enum):
    AGENT = "AGENT"
    HUMAN = "HUMAN"
    ORGANIZATION = "ORGANIZATION"


class PolicyType(str, Enum):
    SPEND_LIMIT = "SPEND_LIMIT"
    ALLOWLIST = "ALLOWLIST"
    BLOCKLIST = "BLOCKLIST"
    APPROVAL_THRESHOLD = "APPROVAL_THRESHOLD"
    TIME_WINDOW = "TIME_WINDOW"


class TransactionStatus(str, Enum):
    SUBMITTED = "SUBMITTED"
    EVALUATED = "EVALUATED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"
    EXECUTED = "EXECUTED"
    FAILED = "FAILED"


class ApprovalAction(str, Enum):
    APPROVE = "APPROVE"
    DENY = "DENY"


class RiskLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
