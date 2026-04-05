"""Decision engine — orchestrates governance evaluation for a transaction.

The decision engine ties together the *policy engine* and *reason codes*
to produce a single ``DecisionResponse`` for every inbound transaction.
"""

from __future__ import annotations

from app.mvp2.core.policy_engine import evaluate_policies
from app.mvp2.schemas.decision import DecisionRequest, DecisionResponse
from app.mvp2.schemas.policy import PolicyRead


def evaluate(
    request: DecisionRequest,
    policies: list[PolicyRead],
) -> DecisionResponse:
    """Run governance evaluation and return a ``DecisionResponse``.

    Parameters
    ----------
    request:
        The inbound decision request.
    policies:
        All policies to evaluate against.

    Returns
    -------
    DecisionResponse
    """
    result, codes, matched = evaluate_policies(
        policies=policies,
        actor_id=request.actor_id,
        action=request.action,
        amount=request.amount,
        currency=request.currency,
    )

    return DecisionResponse(
        transaction_id=request.transaction_id,
        result=result,
        reason_codes=codes,
        matched_policies=matched,
        metadata=request.metadata,
    )
