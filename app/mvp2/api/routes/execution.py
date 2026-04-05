"""Execution routes for CompliAGL MVP 2.

Provides the end-to-end execute endpoint that evaluates a transaction
against governance policy, optionally executes it on-chain, and generates
an immutable proof bundle.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.mvp2.core.decision_engine import evaluate_transaction
from app.mvp2.core.policy_engine import get_policy_for_actor
from app.mvp2.execution.service import execute_if_approved
from app.mvp2.identity.actors import get_actor
from app.mvp2.proof.generator import generate_proof_bundle
from app.mvp2.schemas.execution import ExecuteRequest, ExecuteResponse

router = APIRouter(prefix="/api/mvp2", tags=["mvp2-execution"])


@router.post("/execute", response_model=ExecuteResponse)
async def execute(request: ExecuteRequest) -> ExecuteResponse:
    """Evaluate, execute (if approved), and generate a proof bundle.

    Steps
    -----
    1. Load the actor identified in the transaction.
    2. Load the governance policy bound to that actor.
    3. Evaluate the transaction against the policy to produce a decision.
    4. If the decision is APPROVE, execute the transaction via the
       selected adapter; otherwise execution is ``None``.
    5. Generate an immutable proof bundle regardless of the decision.
    6. Return the combined response containing decision, execution, and
       proof.
    """
    transaction = request.transaction

    # 1. Load actor
    actor = get_actor(transaction.actor_id)
    if actor is None:
        raise HTTPException(
            status_code=404,
            detail=f"Actor not found: {transaction.actor_id}",
        )

    # 2. Load policy
    policy = get_policy_for_actor(actor.actor_id)
    if policy is None:
        raise HTTPException(
            status_code=404,
            detail=f"Policy not found for actor: {actor.actor_id}",
        )

    # 3. Evaluate decision
    decision = evaluate_transaction(transaction, policy)

    # 4. Execute if approved
    execution = await execute_if_approved(transaction, decision, request.adapter)

    # 5. Generate proof bundle
    proof = generate_proof_bundle(actor, transaction, decision, execution)

    # 6. Return combined response
    return ExecuteResponse(
        decision=decision,
        execution=execution,
        proof=proof,
    )
