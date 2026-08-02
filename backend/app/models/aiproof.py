"""Canonical AIProof ORM model.

This is the single, persistent proof record for CompliAGL. It consolidates the
legacy transaction-scoped :class:`app.models.proof_bundle.ProofBundle` and the
in-memory :class:`app.mvp2.schemas.aiproof.AIProofBundle` into one canonical,
persistent domain model.

An **AIProof** captures *who* acted (actor), *what* they intended (intent),
*how* it was governed (policy + decision), *how* it was executed (execution
adapter + optional payment protocol), and *how* it is anchored. A deterministic
``proof_hash`` binds the pre-anchor content together.
"""

from __future__ import annotations

from sqlalchemy import Column, String, Text

from app.core.database import Base


class AIProof(Base):
    """Persistent, canonical AIProof record.

    Column names mirror the :class:`app.mvp2.schemas.aiproof.AIProofBundle`
    domain model so a bundle can be stored and rehydrated without translation.
    JSON-shaped fields (``actor_identity``, ``intent``, ``decision_reason``) are
    stored as ``Text`` containing canonical JSON.
    """

    __tablename__ = "ai_proofs"

    # --- Identity of the proof ---
    proof_id = Column(String, primary_key=True)
    proof_type = Column(String, nullable=False, default="compli402.execution")

    # --- Actor ---
    actor_id = Column(String, nullable=False, index=True)
    actor_identity = Column(Text, nullable=True)  # JSON

    # --- Intent ---
    intent_id = Column(String, nullable=False, index=True)
    intent = Column(Text, nullable=True)  # JSON

    # --- Policy & decision ---
    policy_id = Column(String, nullable=True)
    policy_version = Column(String, nullable=False, default="mvp2")
    decision = Column(String, nullable=False)
    decision_reason = Column(Text, nullable=False, default="[]")  # JSON array

    # --- Execution ---
    execution_adapter = Column(String, nullable=True)
    execution_status = Column(String, nullable=True)

    # --- Payment (optional; e.g. x402) ---
    payment_protocol = Column(String, nullable=True)
    payment_reference = Column(String, nullable=True)
    settlement_chain = Column(String, nullable=True)

    # --- Anchoring ---
    anchor_chain = Column(String, nullable=True, default="algorand")
    anchor_tx_id = Column(String, nullable=True)

    # --- Proof binding ---
    proof_hash = Column(String, nullable=False, index=True)
    created_at = Column(String, nullable=False)
    verification_url = Column(String, nullable=True)
