"""MVP 2 proof routes.

Provides endpoints for generating, listing, and retrieving governance
proof bundles.  All proofs are stored in-memory for MVP 2.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.mvp2.proof.generator import generate_proof
from app.mvp2.schemas.proof import ProofRequest, ProofResponse

router = APIRouter(prefix="/api/mvp2", tags=["mvp2-proof"])

# ---------------------------------------------------------------------------
# In-memory proof store (MVP 2)
# ---------------------------------------------------------------------------
_PROOF_STORE: dict[str, ProofResponse] = {}


@router.post("/proofs/generate", response_model=ProofResponse)
def generate_and_store_proof(request: ProofRequest) -> ProofResponse:
    """Generate an audit proof bundle and store it in-memory."""
    proof = generate_proof(request)
    _PROOF_STORE[proof.proof_hash] = proof
    return proof


@router.get("/proofs", response_model=list[ProofResponse])
def list_proofs() -> list[ProofResponse]:
    """Return all stored proofs."""
    return list(_PROOF_STORE.values())


@router.get("/proofs/{proof_id}", response_model=ProofResponse)
def get_proof(proof_id: str) -> ProofResponse:
    """Return a single proof by its hash."""
    proof = _PROOF_STORE.get(proof_id)
    if proof is None:
        raise HTTPException(status_code=404, detail=f"Proof not found: {proof_id}")
    return proof
