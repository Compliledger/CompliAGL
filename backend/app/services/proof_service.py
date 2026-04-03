"""Proof service — generates and stores proof bundles."""

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.proof_bundle import ProofBundle
from app.utils.hashing import hash_dict


def create_proof_bundle(
    db: Session,
    *,
    transaction_id: str,
    decision: str,
    policy_snapshot: list[dict[str, Any]],
    evaluation_results: list[dict[str, Any]],
) -> ProofBundle:
    """Build a proof bundle with a deterministic hash of the evaluation."""
    proof_hash = hash_dict(
        {
            "transaction_id": transaction_id,
            "decision": decision,
            "policy_snapshot": policy_snapshot,
            "evaluation_results": evaluation_results,
        }
    )

    bundle = ProofBundle(
        transaction_id=transaction_id,
        decision=decision,
        policy_snapshot=json.dumps(policy_snapshot, default=str),
        evaluation_results=json.dumps(evaluation_results, default=str),
        proof_hash=proof_hash,
    )
    db.add(bundle)
    db.commit()
    db.refresh(bundle)
    return bundle


def get_proof_bundle(db: Session, proof_id: str) -> ProofBundle | None:
    return db.query(ProofBundle).filter(ProofBundle.id == proof_id).first()


def list_proof_bundles(
    db: Session,
    transaction_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[ProofBundle]:
    query = db.query(ProofBundle)
    if transaction_id:
        query = query.filter(ProofBundle.transaction_id == transaction_id)
    return query.order_by(ProofBundle.created_at.desc()).offset(skip).limit(limit).all()
