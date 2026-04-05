"""Policy engine — evaluates a transaction against a set of policies.

The policy engine is the source-of-truth for *which* policies apply to
a given actor / action pair, and returns the list of matching policies
together with any triggered reason codes.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.mvp2.core import reason_codes
from app.mvp2.schemas.decision import DecisionResult
from app.mvp2.schemas.policy import PolicyRead, PolicyStatus

# ---------------------------------------------------------------------------
# In-memory policy registry (MVP 2)
# ---------------------------------------------------------------------------

_POLICY_STORE: dict[UUID, PolicyRead] = {}


def seed_demo_policies() -> None:
    """Populate the in-memory registry with demo policies.

    Safe to call multiple times — existing entries are overwritten with the
    canonical demo data.
    """
    demo_policy = PolicyRead(
        id=uuid4(),
        name="Travel Spend Policy",
        description="Governs travel-related agent spending.",
        policy_type="spend",
        rules={
            "max_amount": 500,
            "escalation_threshold": 250,
            "denied_currencies": ["BTC"],
        },
        status=PolicyStatus.ACTIVE,
    )
    _POLICY_STORE[demo_policy.id] = demo_policy


def get_policy(policy_id: UUID) -> PolicyRead | None:
    """Return a policy by *policy_id*, or ``None`` if not found."""
    return _POLICY_STORE.get(policy_id)


def list_policies() -> list[PolicyRead]:
    """Return every policy currently held in the registry."""
    return list(_POLICY_STORE.values())


def evaluate_policies(
    policies: list[PolicyRead],
    actor_id: UUID,
    action: str,
    amount: float,
    currency: str = "USD",
) -> tuple[DecisionResult, list[str], list[UUID]]:
    """Evaluate *policies* against a single transaction.

    Returns
    -------
    result : DecisionResult
        The aggregated outcome.
    triggered_codes : list[str]
        Machine-readable reason codes.
    matched_policy_ids : list[UUID]
        IDs of every policy that matched.
    """
    triggered_codes: list[str] = []
    matched_policy_ids: list[UUID] = []

    active_policies = [p for p in policies if p.status == PolicyStatus.ACTIVE]

    for policy in active_policies:
        rules = policy.rules or {}

        # --- max-amount rule ---
        max_amount = rules.get("max_amount")
        if max_amount is not None and amount > float(max_amount):
            matched_policy_ids.append(policy.id)
            triggered_codes.append(reason_codes.AMOUNT_EXCEEDS_LIMIT)

        # --- denied-currency rule ---
        denied_currencies = rules.get("denied_currencies", [])
        if currency in denied_currencies:
            matched_policy_ids.append(policy.id)
            triggered_codes.append(reason_codes.DENIED_CURRENCY)

        # --- escalation threshold ---
        escalation_threshold = rules.get("escalation_threshold")
        if escalation_threshold is not None and amount > float(escalation_threshold):
            matched_policy_ids.append(policy.id)
            triggered_codes.append(reason_codes.HIGH_RISK_AMOUNT)

    # Deduplicate
    matched_policy_ids = list(dict.fromkeys(matched_policy_ids))

    # Determine aggregate result
    if reason_codes.AMOUNT_EXCEEDS_LIMIT in triggered_codes or reason_codes.DENIED_CURRENCY in triggered_codes:
        result = DecisionResult.DENIED
    elif reason_codes.HIGH_RISK_AMOUNT in triggered_codes:
        result = DecisionResult.ESCALATED
    else:
        result = DecisionResult.APPROVED
        triggered_codes.append(reason_codes.APPROVED_BY_POLICY)

    return result, triggered_codes, matched_policy_ids
