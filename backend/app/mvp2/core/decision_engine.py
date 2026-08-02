"""Decision engine — orchestrates governance evaluation for a transaction.

.. deprecated::
    This in-memory orchestrator is **deprecated**. The canonical, persistent
    decision engine lives in :mod:`app.services.decision_engine`, which reads
    policies from the ``policies`` table and reuses the same deterministic rule
    core (:func:`app.mvp2.core.policy_engine.evaluate_policies`).
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
