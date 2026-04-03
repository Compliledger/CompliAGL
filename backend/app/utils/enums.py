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


class PolicyType(str, Enum):
    SPEND_LIMIT = "SPEND_LIMIT"
    ALLOWLIST = "ALLOWLIST"
    BLOCKLIST = "BLOCKLIST"
    APPROVAL_THRESHOLD = "APPROVAL_THRESHOLD"
    TIME_WINDOW = "TIME_WINDOW"


class ApprovalAction(str, Enum):
    APPROVE = "APPROVE"
    DENY = "DENY"


class ProofStatus(str, Enum):
    GENERATED = "GENERATED"
    ANCHORED = "ANCHORED"
    FAILED = "FAILED"
