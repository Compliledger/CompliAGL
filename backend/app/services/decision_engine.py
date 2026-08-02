"""Canonical deterministic decision engine.

This is the **single** decision engine for CompliAGL. Given an actor intent
(actor identity, action, amount, currency, context) it loads the actor's
**persistent** policies and evaluates them deterministically, returning one of
the canonical outcomes: ``APPROVED``, ``DENIED`` or ``ESCALATED``.

It replaces:

* the transaction-centric ``app/utils/rule_engine.py`` +
  ``app/services/evaluation_service.py`` path, and
* the in-memory ``app/mvp2/core/decision_engine.py`` orchestrator.

The deterministic rule vocabulary is shared with the (now stateless) rule core
:func:`app.mvp2.core.policy_engine.evaluate_policies`, so there is exactly one
place where rules are interpreted.
"""

from __future__ import annotations

from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.mvp2.core.policy_engine import evaluate_policies
from app.mvp2.schemas.decision import DecisionRequest, DecisionResponse
from app.services import policy_repository


def evaluate_intent(
    db: Session,
    *,
    actor_id: UUID,
    action: str,
    amount: float,
    currency: str = "USD",
    transaction_id: UUID | None = None,
    metadata: dict | None = None,
) -> DecisionResponse:
    """Evaluate an actor intent against persistent policies.

    Parameters
    ----------
    db:
        Active database session.
    actor_id / action / amount / currency:
        The intent to govern.
    transaction_id:
        Correlation id for the intent (generated when not supplied).
    metadata:
        Optional operational context, echoed back on the response.

    Returns
    -------
    DecisionResponse
        Canonical decision with ``APPROVED`` / ``DENIED`` / ``ESCALATED``.
    """
    policies = policy_repository.list_active_policies(db)
    result, codes, matched = evaluate_policies(
        policies=policies,
        actor_id=actor_id,
        action=action,
        amount=amount,
        currency=currency,
    )
    return DecisionResponse(
        transaction_id=transaction_id or uuid4(),
        result=result,
        reason_codes=codes,
        matched_policies=matched,
        metadata=metadata,
    )


def evaluate(db: Session, request: DecisionRequest) -> DecisionResponse:
    """Evaluate a :class:`DecisionRequest` (persistent-policy variant)."""
    return evaluate_intent(
        db,
        actor_id=request.actor_id,
        action=request.action,
        amount=request.amount,
        currency=request.currency,
        transaction_id=request.transaction_id,
        metadata=request.metadata,
    )
