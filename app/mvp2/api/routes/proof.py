"""Proof routes for CompliAGL MVP 2.

Provides endpoints for generating, listing, and retrieving governance
proof bundles.  All proofs are stored in-memory for MVP 2.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.mvp2.core.decision_engine import evaluate_transaction
from app.mvp2.core.policy_engine import get_policy_for_actor
from app.mvp2.execution.service import execute_if_approved
from app.mvp2.identity.actors import get_actor
from app.mvp2.proof.generator import generate_proof_bundle
from app.mvp2.schemas.proof import ProofBundle
from app.mvp2.schemas.transaction import TransactionRequest

router = APIRouter(prefix="/api/mvp2", tags=["mvp2-proof"])

# ---------------------------------------------------------------------------
# In-memory proof store (MVP 2)
# ---------------------------------------------------------------------------
_PROOF_STORE: dict[str, ProofBundle] = {}


# ---------------------------------------------------------------------------
# Request schema
# ---------------------------------------------------------------------------
class ProofGenerateRequest(BaseModel):
    """Request body for the proof generation endpoint."""

    actor_id: str
    transaction: TransactionRequest
    adapter: str = Field(default="mock", description="Execution adapter name")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/proofs/generate", response_model=ProofBundle)
async def generate_proof(request: ProofGenerateRequest) -> ProofBundle:
    """Evaluate a transaction, optionally execute it, and generate a proof.

    Steps
    -----
    1. Look up the actor and their policy.
    2. Evaluate the transaction against the policy.
    3. If approved, execute the transaction via the chosen adapter.
    4. Generate an immutable proof bundle.
    5. Store the proof in-memory and return it.
    """
    actor = get_actor(request.actor_id)
    if actor is None:
        raise HTTPException(
            status_code=404,
            detail=f"Actor not found: {request.actor_id}",
        )

    policy = get_policy_for_actor(actor.actor_id)
    if policy is None:
        raise HTTPException(
            status_code=404,
            detail=f"Policy not found for actor: {actor.actor_id}",
        )

    decision = evaluate_transaction(request.transaction, policy)

    execution = await execute_if_approved(
        request.transaction,
        decision,
        adapter_name=request.adapter,
    )

    proof = generate_proof_bundle(actor, request.transaction, decision, execution)

    _PROOF_STORE[proof.proof_id] = proof
    return proof


@router.get("/proofs", response_model=list[ProofBundle])
def list_proofs() -> list[ProofBundle]:
    """Return all stored proofs."""
    return list(_PROOF_STORE.values())


@router.get("/proofs/{proof_id}", response_model=ProofBundle)
def get_proof(proof_id: str) -> ProofBundle:
    """Return a single proof by its ID."""
    proof = _PROOF_STORE.get(proof_id)
    if proof is None:
        raise HTTPException(status_code=404, detail=f"Proof not found: {proof_id}")
    return proof
