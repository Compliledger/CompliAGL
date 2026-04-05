"""Decision engine – evaluates a transaction against a governance policy.

Combines the *policy_engine* helpers with *reason_codes* to produce a
:class:`DecisionResult` for every inbound :class:`TransactionRequest`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from app.mvp2.core.policy_engine import (
    amount_valid,
    asset_allowed,
    chain_allowed,
    vendor_allowed,
)
from app.mvp2.core.reason_codes import (
    ESCALATION_THRESHOLD_EXCEEDED,
    INVALID_AMOUNT,
    WITHIN_POLICY,
)
from app.mvp2.schemas.decision import DecisionResult, DecisionStatus
from app.mvp2.schemas.policy import PolicyDefinition
from app.mvp2.schemas.transaction import TransactionRequest


def evaluate_transaction(
    transaction: TransactionRequest,
    policy: PolicyDefinition,
) -> DecisionResult:
    """Evaluate *transaction* against *policy* and return a decision.

    Decision logic
    --------------
    1. ``amount`` must be > 0.
    2. ``vendor`` must be in ``allowed_vendors``.
    3. ``chain`` must be in ``allowed_chains``.
    4. ``asset_symbol`` must be in ``allowed_assets``.
    5. If ``amount`` > ``max_amount`` → **DENY**.
    6. If ``amount`` > ``escalation_threshold`` (and ≤ ``max_amount``) → **ESCALATE**.
    7. Otherwise → **APPROVE**.

    Any hard-validation failure (steps 1-5) results in **DENY** with *all*
    applicable reason codes collected by :func:`amount_valid`.
    """

    is_valid, reason_codes = amount_valid(transaction, policy)

    if not is_valid:
        # Hard deny – surface every reason code produced by the validation.
        return DecisionResult(
            decision=DecisionStatus.DENY,
            reason_codes=reason_codes,
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # All hard checks passed; evaluate escalation threshold.
    if transaction.amount > policy.escalation_threshold:
        return DecisionResult(
            decision=DecisionStatus.ESCALATE,
            reason_codes=[ESCALATION_THRESHOLD_EXCEEDED],
            policy_id=policy.policy_id,
            policy_version=policy.policy_version,
            timestamp=datetime.now(timezone.utc).isoformat(),
        )

    # Within policy – fully approved.
    return DecisionResult(
        decision=DecisionStatus.APPROVE,
        reason_codes=[WITHIN_POLICY],
        policy_id=policy.policy_id,
        policy_version=policy.policy_version,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
