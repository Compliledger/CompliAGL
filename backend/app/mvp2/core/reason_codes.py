"""Reason codes emitted by the decision and policy engines.

Each code is a short, machine-readable string that describes *why*
a particular decision was reached.  API consumers can use these codes
to drive UI messaging, audit trails, and downstream logic.
"""

from __future__ import annotations

# --- Deny reason codes ---
AMOUNT_EXCEEDS_LIMIT = "AMOUNT_EXCEEDS_LIMIT"
DENIED_CURRENCY = "DENIED_CURRENCY"
POLICY_VIOLATION = "POLICY_VIOLATION"
ACTOR_SUSPENDED = "ACTOR_SUSPENDED"
UNKNOWN_ACTOR = "UNKNOWN_ACTOR"

# --- Escalation reason codes ---
HIGH_RISK_AMOUNT = "HIGH_RISK_AMOUNT"
MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
MULTI_SIG_REQUIRED = "MULTI_SIG_REQUIRED"

# --- Approval reason codes ---
APPROVED_BY_POLICY = "APPROVED_BY_POLICY"
APPROVED_WITHIN_LIMITS = "APPROVED_WITHIN_LIMITS"

ALL_REASON_CODES: set[str] = {
    AMOUNT_EXCEEDS_LIMIT,
    DENIED_CURRENCY,
    POLICY_VIOLATION,
    ACTOR_SUSPENDED,
    UNKNOWN_ACTOR,
    HIGH_RISK_AMOUNT,
    MANUAL_REVIEW_REQUIRED,
    MULTI_SIG_REQUIRED,
    APPROVED_BY_POLICY,
    APPROVED_WITHIN_LIMITS,
}
