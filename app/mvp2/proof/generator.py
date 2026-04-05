"""Proof generator — builds and hashes audit proof bundles.

This module exposes :func:`generate_proof_bundle`, the single entry-point
for producing a :class:`~app.mvp2.schemas.proof.ProofBundle` from the
governance artefacts collected during a transaction lifecycle.
"""

from __future__ import annotations

import uuid

from app.mvp2.proof.hashing import sha256_json
from app.mvp2.proof.schema import build_proof_payload
from app.mvp2.schemas.actor import ActorIdentity
from app.mvp2.schemas.decision import DecisionResult
from app.mvp2.schemas.proof import ProofBundle
from app.mvp2.schemas.transaction import ExecutionResult, TransactionRequest


def generate_proof_bundle(
    actor: ActorIdentity,
    transaction: TransactionRequest,
    decision: DecisionResult,
    execution: ExecutionResult | None,
) -> ProofBundle:
    """Generate an immutable proof bundle for a governed transaction.

    The function assembles a canonical payload from the supplied
    governance artefacts, hashes it with SHA-256, and wraps the result
    in a :class:`ProofBundle`.

    Parameters
    ----------
    actor:
        The identity of the actor who initiated the transaction.
    transaction:
        The original transaction request under governance.
    decision:
        The governance decision rendered for the transaction.
    execution:
        The on-chain execution result, or *None* when the decision is
        DENY or ESCALATE and no execution took place.

    Returns
    -------
    ProofBundle
        A fully populated proof record ready for storage or anchoring.
    """
    payload = build_proof_payload(actor, transaction, decision, execution)
    payload_hash = sha256_json(payload)
    proof_id = str(uuid.uuid4())

    return ProofBundle(
        proof_id=proof_id,
        actor_id=payload["actor_id"],
        transaction_id=payload["transaction_id"],
        decision=payload["decision"],
        reason_codes=payload["reason_codes"],
        policy_id=payload["policy_id"],
        policy_version=payload["policy_version"],
        execution_tx_hash=payload["execution_tx_hash"],
        execution_chain=payload["execution_chain"],
        execution_status=payload["execution_status"],
        timestamp=payload["timestamp"],
        hash=payload_hash,
    )
