"""Evaluation service — orchestrates rule engine, proof generation, and audit logging."""

import json

from sqlalchemy.orm import Session

from app.models.transaction import Transaction
from app.services.policy_service import list_policies, _parse_policy
from app.services.proof_service import create_proof_bundle
from app.services.audit_service import log_event
from app.utils.rule_engine import evaluate_policies


def evaluate_transaction(db: Session, transaction: Transaction) -> dict:
    """Run all active policies against a transaction and persist the results."""

    # Build transaction context dict consumed by the rule engine
    tx_ctx = {
        "agent_id": transaction.agent_id,
        "recipient": transaction.recipient,
        "amount": transaction.amount,
        "currency": transaction.currency,
    }

    # Gather active policies
    active_policies_orm = list_policies(db, active_only=True)
    policies = [_parse_policy(p) for p in active_policies_orm]

    # Evaluate
    decision, results = evaluate_policies(tx_ctx, policies)

    # Update transaction status
    transaction.status = decision.value
    db.commit()
    db.refresh(transaction)

    # Create proof bundle
    proof = create_proof_bundle(
        db,
        transaction_id=transaction.id,
        decision=decision.value,
        policy_snapshot=policies,
        evaluation_results=results,
    )

    # Audit log
    log_event(
        db,
        entity_type="transaction",
        entity_id=transaction.id,
        action=f"EVALUATED:{decision.value}",
        details=json.dumps({"results": results, "proof_id": proof.id}),
        performed_by="system",
    )

    return {
        "transaction_id": transaction.id,
        "decision": decision.value,
        "results": results,
        "proof_bundle_id": proof.id,
    }
