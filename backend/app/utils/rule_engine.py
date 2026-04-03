"""CompliAGL rule engine — evaluates a transaction against an agent's active policy.

The engine applies rules in a strict order (1–15) and returns a structured
decision with reason codes, a summary, risk level, and approval flag.

Each rule is evaluated sequentially; the first DENIED or ESCALATED result
short-circuits the remaining checks.
"""

from __future__ import annotations

import json
from typing import Any


def _parse_json_list(raw: str | list | None) -> list[str]:
    """Safely parse a JSON-encoded list or return as-is if already a list."""
    if raw is None:
        return []
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else []
    except (json.JSONDecodeError, TypeError):
        return []


def evaluate_transaction_rules(
    *,
    agent: dict[str, Any] | None,
    policy: dict[str, Any] | None,
    transaction: dict[str, Any],
    daily_spend_total: float = 0.0,
    daily_transaction_count: int = 0,
) -> dict[str, Any]:
    """Evaluate a transaction against the agent's active policy.

    Parameters
    ----------
    agent:
        Agent dict with at least ``status`` (may be *None* if not found).
    policy:
        The active policy dict for the agent (may be *None*).
    transaction:
        Transaction dict with ``amount``, ``vendor``, ``chain``,
        ``asset_symbol``.
    daily_spend_total:
        Total approved + pending spend for the current day.
    daily_transaction_count:
        Number of transactions already recorded today.

    Returns
    -------
    dict with keys:
        - ``decision_result`` – ``"APPROVED"`` | ``"DENIED"`` | ``"ESCALATED"``
        - ``reason_codes``    – list[str]
        - ``decision_summary``– human-readable explanation
        - ``risk_level``      – ``"LOW"`` | ``"MEDIUM"`` | ``"HIGH"``
        - ``requires_approval`` – bool
    """

    amount = float(transaction.get("amount", 0))
    vendor = (transaction.get("vendor") or "").strip()
    chain = (transaction.get("chain") or "").strip()
    asset_symbol = (transaction.get("asset_symbol") or "").strip()

    # ------------------------------------------------------------------ 1
    if agent is None or agent.get("status") != "ACTIVE":
        return _result(
            "DENIED",
            ["AGENT_INACTIVE"],
            "Agent is not active or does not exist",
            "HIGH",
            False,
        )

    # ------------------------------------------------------------------ 2
    if policy is None:
        return _result(
            "DENIED",
            ["POLICY_NOT_FOUND"],
            "No active policy found for agent",
            "HIGH",
            False,
        )

    # ------------------------------------------------------------------ 3
    if amount <= 0:
        return _result(
            "DENIED",
            ["INVALID_AMOUNT"],
            "Transaction amount must be greater than zero",
            "HIGH",
            False,
        )

    # ------------------------------------------------------------------ 4
    blocked_vendors = _parse_json_list(policy.get("blocked_vendors"))
    if vendor and vendor in blocked_vendors:
        return _result(
            "DENIED",
            ["VENDOR_BLOCKED"],
            f"Vendor '{vendor}' is blocked by policy",
            "HIGH",
            False,
        )

    # ------------------------------------------------------------------ 5
    blocked_chains = _parse_json_list(policy.get("blocked_chains"))
    if chain and chain in blocked_chains:
        return _result(
            "DENIED",
            ["CHAIN_BLOCKED"],
            f"Chain '{chain}' is blocked by policy",
            "HIGH",
            False,
        )

    # ------------------------------------------------------------------ 6
    blocked_assets = _parse_json_list(policy.get("blocked_asset_symbols"))
    if asset_symbol and asset_symbol in blocked_assets:
        return _result(
            "DENIED",
            ["ASSET_BLOCKED"],
            f"Asset '{asset_symbol}' is blocked by policy",
            "HIGH",
            False,
        )

    # ------------------------------------------------------------------ 7
    allowed_vendors = _parse_json_list(policy.get("allowed_vendors"))
    if allowed_vendors and vendor and vendor not in allowed_vendors:
        return _result(
            "DENIED",
            ["VENDOR_NOT_ALLOWED"],
            f"Vendor '{vendor}' is not in the allowed vendors list",
            "HIGH",
            False,
        )

    # ------------------------------------------------------------------ 8
    allowed_chains = _parse_json_list(policy.get("allowed_chains"))
    if allowed_chains and chain and chain not in allowed_chains:
        return _result(
            "DENIED",
            ["CHAIN_NOT_ALLOWED"],
            f"Chain '{chain}' is not in the allowed chains list",
            "HIGH",
            False,
        )

    # ------------------------------------------------------------------ 9
    allowed_assets = _parse_json_list(policy.get("allowed_asset_symbols"))
    if allowed_assets and asset_symbol and asset_symbol not in allowed_assets:
        return _result(
            "DENIED",
            ["ASSET_NOT_ALLOWED"],
            f"Asset '{asset_symbol}' is not in the allowed asset symbols list",
            "HIGH",
            False,
        )

    # ----------------------------------------------------------------- 10
    per_tx_limit = policy.get("per_tx_limit")
    if per_tx_limit is not None and amount > float(per_tx_limit):
        return _result(
            "DENIED",
            ["PER_TX_LIMIT_EXCEEDED"],
            f"Amount {amount} exceeds per-transaction limit of {per_tx_limit}",
            "HIGH",
            False,
        )

    # ----------------------------------------------------------------- 11
    daily_budget = policy.get("daily_budget")
    if daily_budget is not None and (daily_spend_total + amount) > float(daily_budget):
        return _result(
            "DENIED",
            ["DAILY_BUDGET_EXCEEDED"],
            f"Daily spend would reach {daily_spend_total + amount}, exceeding budget of {daily_budget}",
            "HIGH",
            False,
        )

    # ----------------------------------------------------------------- 12
    max_tx = policy.get("max_transactions_per_day")
    if max_tx is not None and daily_transaction_count >= int(max_tx):
        return _result(
            "DENIED",
            ["MAX_TX_COUNT_EXCEEDED"],
            f"Daily transaction count ({daily_transaction_count}) has reached the limit of {max_tx}",
            "HIGH",
            False,
        )

    # ----------------------------------------------------------------- 13
    identity_threshold = policy.get("require_identity_check_above_amount")
    if identity_threshold is not None and amount > float(identity_threshold):
        return _result(
            "ESCALATED",
            ["IDENTITY_CHECK_REQUIRED"],
            f"Amount {amount} exceeds identity-check threshold of {identity_threshold}",
            "MEDIUM",
            True,
        )

    # ----------------------------------------------------------------- 14
    if policy.get("require_approval_above_threshold"):
        escalation_threshold = policy.get("escalation_threshold")
        if escalation_threshold is not None and amount >= float(escalation_threshold):
            return _result(
                "ESCALATED",
                ["THRESHOLD_REQUIRES_APPROVAL"],
                f"Amount {amount} meets/exceeds escalation threshold of {escalation_threshold}",
                "MEDIUM",
                True,
            )

    # ----------------------------------------------------------------- 15
    escalation_threshold = policy.get("escalation_threshold")
    risk = "LOW"
    if escalation_threshold is not None and amount >= float(escalation_threshold):
        risk = "MEDIUM"

    return _result(
        "APPROVED",
        ["WITHIN_POLICY"],
        "Transaction approved — within policy limits",
        risk,
        False,
    )


def _result(
    decision_result: str,
    reason_codes: list[str],
    decision_summary: str,
    risk_level: str,
    requires_approval: bool,
) -> dict[str, Any]:
    """Build a canonical rule-engine result dict."""
    return {
        "decision_result": decision_result,
        "reason_codes": reason_codes,
        "decision_summary": decision_summary,
        "risk_level": risk_level,
        "requires_approval": requires_approval,
    }
