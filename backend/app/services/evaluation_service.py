"""Evaluation service — orchestrates rule engine, proof generation, and audit logging."""

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session
from sqlalchemy import func as sa_func

from app.models.agent import Agent
from app.models.policy import Policy
from app.models.transaction import Transaction
from app.services.proof_service import create_proof_bundle
from app.services.audit_service import log_event
from app.utils.rule_engine import evaluate_transaction_rules


def _policy_to_eval_dict(policy: Policy) -> dict[str, Any]:
    """Convert a Policy ORM object to a plain dict for the rule engine."""
    return {
        "id": policy.id,
        "agent_id": policy.agent_id,
        "name": policy.name,
        "blocked_vendors": policy.blocked_vendors,
        "blocked_chains": policy.blocked_chains,
        "blocked_asset_symbols": policy.blocked_asset_symbols,
        "allowed_vendors": policy.allowed_vendors,
        "allowed_chains": policy.allowed_chains,
        "allowed_asset_symbols": policy.allowed_asset_symbols,
        "per_tx_limit": policy.per_tx_limit,
        "daily_budget": policy.daily_budget,
        "max_transactions_per_day": policy.max_transactions_per_day,
        "require_identity_check_above_amount": policy.require_identity_check_above_amount,
        "require_approval_above_threshold": policy.require_approval_above_threshold,
        "escalation_threshold": policy.escalation_threshold,
    }


def _get_daily_spend_total(db: Session, agent_id: str) -> float:
    """Sum of amounts for today's APPROVED or SUBMITTED transactions."""
    start_of_day = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    result = (
        db.query(sa_func.coalesce(sa_func.sum(Transaction.amount), 0.0))
        .filter(
            Transaction.agent_id == agent_id,
            Transaction.status.in_(["APPROVED", "SUBMITTED", "ESCALATED"]),
            Transaction.created_at >= start_of_day,
        )
        .scalar()
    )
    return float(result)


def _get_daily_transaction_count(db: Session, agent_id: str) -> int:
    """Count of today's transactions (any status)."""
    start_of_day = datetime.now(timezone.utc).replace(
        hour=0, minute=0, second=0, microsecond=0,
    )
    result = (
        db.query(sa_func.count(Transaction.id))
        .filter(
            Transaction.agent_id == agent_id,
            Transaction.created_at >= start_of_day,
        )
        .scalar()
    )
    return int(result)


def evaluate_transaction(db: Session, transaction_id: str) -> dict[str, Any]:
    """Load a submitted transaction, evaluate it against the agent's active
    policy, persist the decision, create an audit log entry and proof bundle,
    and return the evaluation result.

    Parameters
    ----------
    db:
        Active SQLAlchemy session.
    transaction_id:
        Primary key of the transaction to evaluate.

    Returns
    -------
    dict containing the decision, proof bundle summary, and transaction id.
    """

    # --- Load transaction --------------------------------------------------
    transaction = (
        db.query(Transaction)
        .filter(Transaction.id == transaction_id)
        .first()
    )
    if transaction is None:
        return {
            "transaction_id": transaction_id,
            "decision_result": "DENIED",
            "reason_codes": ["TRANSACTION_NOT_FOUND"],
            "decision_summary": "Transaction not found",
            "risk_level": "HIGH",
            "requires_approval": False,
            "proof_bundle_summary": None,
        }

    # --- Load agent --------------------------------------------------------
    agent = (
        db.query(Agent)
        .filter(Agent.id == transaction.agent_id)
        .first()
    )
    agent_dict = (
        {"id": agent.id, "name": agent.name, "status": agent.status}
        if agent
        else None
    )

    # --- Load active policy for this agent ---------------------------------
    policy = (
        db.query(Policy)
        .filter(
            Policy.agent_id == transaction.agent_id,
            Policy.is_active.is_(True),
        )
        .first()
    )
    policy_dict = _policy_to_eval_dict(policy) if policy else None

    # --- Compute daily aggregates ------------------------------------------
    daily_spend = _get_daily_spend_total(db, transaction.agent_id)
    daily_count = _get_daily_transaction_count(db, transaction.agent_id)

    # --- Build transaction context -----------------------------------------
    tx_dict = {
        "id": transaction.id,
        "agent_id": transaction.agent_id,
        "amount": transaction.amount,
        "vendor": transaction.vendor,
        "chain": transaction.chain,
        "asset_symbol": transaction.asset_symbol,
        "recipient": transaction.recipient,
        "currency": transaction.currency,
    }

    # --- Evaluate rules ----------------------------------------------------
    result = evaluate_transaction_rules(
        agent=agent_dict,
        policy=policy_dict,
        transaction=tx_dict,
        daily_spend_total=daily_spend,
        daily_transaction_count=daily_count,
    )

    # --- Persist decision on transaction -----------------------------------
    decision_result = result["decision_result"]
    transaction.decision_result = decision_result
    if decision_result == "APPROVED":
        transaction.status = "APPROVED"
    elif decision_result == "DENIED":
        transaction.status = "DENIED"
    elif decision_result == "ESCALATED":
        transaction.status = "ESCALATED"
    db.commit()
    db.refresh(transaction)

    # --- Create proof bundle -----------------------------------------------
    proof = create_proof_bundle(
        db,
        transaction_id=transaction.id,
        decision=decision_result,
        policy_snapshot=[policy_dict] if policy_dict else [],
        evaluation_results=[result],
    )

    # --- Audit log ---------------------------------------------------------
    log_event(
        db,
        entity_type="transaction",
        entity_id=transaction.id,
        action=f"EVALUATED:{decision_result}",
        details=json.dumps(
            {
                "reason_codes": result["reason_codes"],
                "risk_level": result["risk_level"],
                "proof_id": proof.id,
            },
            default=str,
        ),
        performed_by="system",
    )

    # --- Build response ----------------------------------------------------
    return {
        "transaction_id": transaction.id,
        "decision_result": decision_result,
        "reason_codes": result["reason_codes"],
        "decision_summary": result["decision_summary"],
        "risk_level": result["risk_level"],
        "requires_approval": result["requires_approval"],
        "proof_bundle_summary": {
            "proof_bundle_id": proof.id,
            "proof_hash": proof.proof_hash,
            "decision": proof.decision,
            "created_at": str(proof.created_at),
        },
    }
