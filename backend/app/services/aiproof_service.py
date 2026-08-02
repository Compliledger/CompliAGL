"""Legacy x402 AIProof-bundle persistence service (demo surface).

.. deprecated::
    Superseded by the canonical AIProof service
    :mod:`app.services.canonical.aiproof.service` (schema:
    :class:`app.schemas.canonical.aiproof.AIProof`, storage:
    :class:`app.models.canonical_aiproof.CanonicalAIProof`). Use the canonical
    AIProof for the governance-lifecycle proof, canonical serialization, signing
    and the CompliLedger handoff.

This service persists the legacy compli402 x402 demo ``AIProofBundle`` and is
retained only for that flow. It maps the
:class:`app.mvp2.schemas.aiproof.AIProofBundle` domain model to and from the
legacy :class:`app.models.aiproof.AIProof` ORM row.
"""

from __future__ import annotations

import json

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.aiproof import AIProof
from app.mvp2.schemas.aiproof import AIProofBundle

# Fields that are stored as JSON text in the database.
_JSON_FIELDS = ("actor_identity", "intent", "decision_reason")


def _bundle_to_columns(bundle: AIProofBundle) -> dict:
    """Return an AIProof column dict from an :class:`AIProofBundle`."""
    data = bundle.model_dump(mode="json")
    for field in _JSON_FIELDS:
        value = data.get(field)
        data[field] = json.dumps(value) if value is not None else None
    # decision_reason must never be NULL (list is default) — store "[]".
    if data.get("decision_reason") is None:
        data["decision_reason"] = "[]"
    return data


def _row_to_dict(row: AIProof) -> dict:
    """Return a JSON-serialisable dict for an AIProof row."""
    data = {
        column.name: getattr(row, column.name)
        for column in AIProof.__table__.columns
    }
    for field in _JSON_FIELDS:
        raw = data.get(field)
        data[field] = json.loads(raw) if raw is not None else None
    return data


def store_proof(db: Session, bundle: AIProofBundle) -> dict:
    """Persist an :class:`AIProofBundle`, returning its serialised form.

    If a proof with the same ``proof_id`` already exists it is updated (this
    keeps the operation idempotent and allows post-hash fields such as
    ``anchor_tx_id`` / ``verification_url`` to be written after anchoring).
    """
    columns = _bundle_to_columns(bundle)
    existing = db.get(AIProof, columns["proof_id"])
    if existing is None:
        row = AIProof(**columns)
        db.add(row)
    else:
        for key, value in columns.items():
            setattr(existing, key, value)
        row = existing
    db.commit()
    db.refresh(row)
    return _row_to_dict(row)


def get_by_hash(db: Session, proof_hash: str) -> dict | None:
    """Return a stored proof by its ``proof_hash`` or ``None``."""
    row = db.execute(
        select(AIProof).where(AIProof.proof_hash == proof_hash)
    ).scalar_one_or_none()
    return _row_to_dict(row) if row is not None else None


def get_latest(db: Session) -> dict | None:
    """Return the most recently created proof or ``None``."""
    row = db.execute(
        select(AIProof).order_by(AIProof.created_at.desc())
    ).scalars().first()
    return _row_to_dict(row) if row is not None else None


def list_proofs(db: Session) -> list[dict]:
    """Return all stored proofs (oldest first)."""
    rows = db.execute(
        select(AIProof).order_by(AIProof.created_at.asc())
    ).scalars().all()
    return [_row_to_dict(row) for row in rows]


def count_proofs(db: Session) -> int:
    """Return the number of stored proofs."""
    return db.query(AIProof).count()
