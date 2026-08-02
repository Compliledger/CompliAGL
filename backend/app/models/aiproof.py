"""Legacy x402 AIProof ORM model (demo surface).

.. deprecated::
    Superseded by the single canonical persistent AIProof —
    :class:`app.models.canonical_aiproof.CanonicalAIProof` (schema:
    :class:`app.schemas.canonical.aiproof.AIProof`). The canonical AIProof covers
    the complete governance lifecycle, is RFC 8785 canonicalized, SHA-256 hashed
    and digitally signed, references sensitive evidence instead of embedding it,
    and is formally handed off to CompliLedger.

This ``AIProof`` table backs only the compli402 x402 hackathon-demo flow. It
consolidated the earlier transaction-scoped :class:`ProofBundle` and the
in-memory ``AIProofBundle`` demo store; the governance-lifecycle proof is now the
canonical AIProof above.

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
