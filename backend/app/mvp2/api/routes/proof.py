"""MVP 2 proof routes."""

from __future__ import annotations

from fastapi import APIRouter

from app.mvp2.proof.generator import generate_proof
from app.mvp2.schemas.proof import ProofRequest, ProofResponse

router = APIRouter(prefix="/proofs", tags=["mvp2-proofs"])


@router.post("/", response_model=ProofResponse)
async def create_proof(request: ProofRequest) -> ProofResponse:
    """Generate an audit proof bundle for a governance decision."""
    return generate_proof(request)
