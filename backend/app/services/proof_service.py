"""Proof service — generates and stores proof bundles."""

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.proof_bundle import ProofBundle
from app.utils.hashing import compute_bundle_hash
from app.utils.timestamps import utc_now


def create_proof_bundle(
    db: Session,
    *,
    transaction_id: str,
    agent_id: str,
    entity_id: str,
    rule_version_used: str,
    decision_result: str,
    evaluation_context: list[dict[str, Any]] | dict[str, Any],
    reason_codes: list[dict[str, Any]] | list[str],
) -> ProofBundle:
    """Build a proof bundle with a deterministic hash of the evaluation.

    Exactly one proof bundle is created per evaluation.  The ``bundle_hash``
    is computed from a canonical payload containing the fields specified in
    the requirements (module, entity_id, rule_version_used, decision_result,
    evaluation_context, reason_codes, timestamp).
    """
    module = "CompliAGL"
    ts = utc_now()
    ts_iso = ts.isoformat()

    bundle_hash = compute_bundle_hash(
        module=module,
        entity_id=entity_id,
        rule_version_used=rule_version_used,
        decision_result=decision_result,
        evaluation_context=evaluation_context,
        reason_codes=reason_codes,
        timestamp=ts_iso,
    )

    bundle = ProofBundle(
        transaction_id=transaction_id,
        agent_id=agent_id,
        module=module,
        entity_id=entity_id,
        rule_version_used=rule_version_used,
        decision_result=decision_result,
        evaluation_context=json.dumps(evaluation_context, sort_keys=True, separators=(",", ":"), default=str),
        reason_codes=json.dumps(reason_codes, sort_keys=True, separators=(",", ":"), default=str),
        timestamp=ts,
        bundle_hash=bundle_hash,
        proof_status="GENERATED",
    )
    db.add(bundle)
    db.commit()
    db.refresh(bundle)
    return bundle


def get_proof_bundle(db: Session, proof_id: str) -> ProofBundle | None:
    return db.query(ProofBundle).filter(ProofBundle.id == proof_id).first()


def get_proof_by_transaction(db: Session, transaction_id: str) -> ProofBundle | None:
    return db.query(ProofBundle).filter(ProofBundle.transaction_id == transaction_id).first()


def list_proof_bundles(
    db: Session,
    transaction_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
) -> list[ProofBundle]:
    query = db.query(ProofBundle)
    if transaction_id:
        query = query.filter(ProofBundle.transaction_id == transaction_id)
    return query.order_by(ProofBundle.timestamp.desc()).offset(skip).limit(limit).all()
