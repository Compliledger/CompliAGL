"""Proof generator — builds and hashes audit proof bundles."""

from __future__ import annotations

from datetime import datetime, timezone

from app.mvp2.proof.hashing import sha256_hash
from app.mvp2.proof.schema import ProofPayload
from app.mvp2.schemas.proof import ProofRequest, ProofResponse, ProofStatus


def generate_proof(request: ProofRequest) -> ProofResponse:
    """Generate a proof bundle for the given request.

    Builds a canonical payload, hashes it, and returns a
    ``ProofResponse`` with the resulting digest.
    """
    payload = ProofPayload(
        transaction_id=request.transaction_id,
        decision_result=request.decision_result,
        reason_codes=request.reason_codes,
        timestamp=datetime.now(timezone.utc).isoformat(),
        metadata=request.metadata,
    )

    proof_hash = sha256_hash(payload.model_dump())

    return ProofResponse(
        transaction_id=request.transaction_id,
        proof_hash=proof_hash,
        status=ProofStatus.GENERATED,
        payload=payload.model_dump(),
        metadata=request.metadata,
    )
