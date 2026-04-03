"""Simple rule engine for policy evaluation.

Each rule is a callable that receives a transaction context dict and returns
a tuple of (passed: bool, reason: str).  The engine runs all applicable rules
and aggregates the result into a final DecisionStatus.
"""

from __future__ import annotations

from typing import Any, Callable

from app.utils.enums import DecisionStatus

# Type alias for a single rule function
RuleFn = Callable[[dict[str, Any], dict[str, Any]], tuple[bool, str]]


def _check_spend_limit(
    tx_ctx: dict[str, Any], policy_params: dict[str, Any]
) -> tuple[bool, str]:
    """Deny if the transaction amount exceeds the policy limit."""
    limit = float(policy_params.get("limit", 0))
    amount = float(tx_ctx.get("amount", 0))
    if amount > limit:
        return False, f"Amount {amount} exceeds spend limit {limit}"
    return True, "Within spend limit"


def _check_allowlist(
    tx_ctx: dict[str, Any], policy_params: dict[str, Any]
) -> tuple[bool, str]:
    """Deny if the recipient is not on the allowlist."""
    allowed: list[str] = policy_params.get("addresses", [])
    recipient = tx_ctx.get("recipient", "")
    if allowed and recipient not in allowed:
        return False, f"Recipient {recipient} not on allowlist"
    return True, "Recipient is allowed"


def _check_blocklist(
    tx_ctx: dict[str, Any], policy_params: dict[str, Any]
) -> tuple[bool, str]:
    """Deny if the recipient is on the blocklist."""
    blocked: list[str] = policy_params.get("addresses", [])
    recipient = tx_ctx.get("recipient", "")
    if recipient in blocked:
        return False, f"Recipient {recipient} is blocklisted"
    return True, "Recipient is not blocklisted"


def _check_approval_threshold(
    tx_ctx: dict[str, Any], policy_params: dict[str, Any]
) -> tuple[bool, str]:
    """Escalate if the amount exceeds the threshold but is under the hard cap."""
    threshold = float(policy_params.get("threshold", 0))
    amount = float(tx_ctx.get("amount", 0))
    if amount > threshold:
        return False, f"Amount {amount} exceeds approval threshold {threshold} — escalation required"
    return True, "Below approval threshold"


BUILT_IN_RULES: dict[str, RuleFn] = {
    "SPEND_LIMIT": _check_spend_limit,
    "ALLOWLIST": _check_allowlist,
    "BLOCKLIST": _check_blocklist,
    "APPROVAL_THRESHOLD": _check_approval_threshold,
}


def evaluate_policies(
    tx_ctx: dict[str, Any],
    policies: list[dict[str, Any]],
) -> tuple[DecisionStatus, list[dict[str, Any]]]:
    """Evaluate *policies* against a transaction context.

    Returns the aggregate decision and a list of per-rule results.
    """
    results: list[dict[str, Any]] = []
    needs_escalation = False

    for policy in policies:
        policy_type: str = policy.get("policy_type", "")
        params: dict[str, Any] = policy.get("parameters", {})
        rule_fn = BUILT_IN_RULES.get(policy_type)

        if rule_fn is None:
            results.append(
                {"policy_id": policy.get("id"), "passed": True, "reason": "Unknown policy type — skipped"}
            )
            continue

        passed, reason = rule_fn(tx_ctx, params)
        results.append({"policy_id": policy.get("id"), "passed": passed, "reason": reason})

        if not passed:
            if policy_type == "APPROVAL_THRESHOLD":
                needs_escalation = True
            else:
                return DecisionStatus.DENIED, results

    if needs_escalation:
        return DecisionStatus.ESCALATED, results

    return DecisionStatus.APPROVED, results
