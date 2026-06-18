"""AIProof generator — assembles and deterministically hashes AIProof bundles.

This builds the canonical :class:`AIProofBundle` from the components of a
governed execution (actor, intent, decision, execution result) and computes a
deterministic ``proof_hash`` that excludes post-hash fields.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from app.mvp2.proof.hashing import sha256_hash
from app.mvp2.schemas.aiproof import AIProofBundle


def _utc_now_iso() -> str:
    """Return the current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def compute_proof_hash(bundle: AIProofBundle) -> str:
    """Return the deterministic SHA-256 hash of *bundle*.

    The hash is computed over the bundle's :meth:`AIProofBundle.hashable_payload`,
    which excludes post-hash fields (``proof_hash``, ``anchor_tx_id``,
    ``verification_url``).
    """
    return sha256_hash(bundle.hashable_payload())


def build_aiproof(
    *,
    actor_id: str,
    intent_id: str,
    decision: str,
    decision_reason: list[str] | None = None,
    actor_identity: dict | None = None,
    intent: dict | None = None,
    policy_id: str | None = None,
    policy_version: str = "mvp2",
    execution_adapter: str | None = None,
    execution_status: str | None = None,
    payment_protocol: str = "x402",
    payment_reference: str | None = None,
    settlement_chain: str | None = None,
    anchor_chain: str = "algorand",
    proof_type: str = "compli402.execution",
    created_at: str | None = None,
    proof_id: str | None = None,
) -> AIProofBundle:
    """Build an :class:`AIProofBundle` and bind it with a deterministic hash.

    Post-hash fields (``anchor_tx_id``, ``verification_url``) are intentionally
    left unset; they are populated after the proof has been hashed and anchored.
    """
    bundle = AIProofBundle(
        proof_id=proof_id or str(uuid4()),
        proof_type=proof_type,
        actor_id=actor_id,
        actor_identity=actor_identity,
        intent_id=intent_id,
        intent=intent,
        policy_id=policy_id,
        policy_version=policy_version,
        decision=decision,
        decision_reason=decision_reason or [],
        execution_adapter=execution_adapter,
        execution_status=execution_status,
        payment_protocol=payment_protocol,
        payment_reference=payment_reference,
        settlement_chain=settlement_chain,
        anchor_chain=anchor_chain,
        created_at=created_at or _utc_now_iso(),
    )
    bundle.proof_hash = compute_proof_hash(bundle)
    return bundle
