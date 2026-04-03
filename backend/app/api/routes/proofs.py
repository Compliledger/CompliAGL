"""Proof bundle routes — read-only access to compliance proofs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.proof_bundle import ProofBundleResponse
from app.services import proof_service

router = APIRouter(prefix="/proofs", tags=["proofs"])


@router.get("/", response_model=list[ProofBundleResponse])
def list_proofs(transaction_id: str | None = None, skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return proof_service.list_proof_bundles(db, transaction_id=transaction_id, skip=skip, limit=limit)


@router.get("/{proof_id}", response_model=ProofBundleResponse)
def get_proof(proof_id: str, db: Session = Depends(get_db)):
    proof = proof_service.get_proof_bundle(db, proof_id)
    if not proof:
        raise HTTPException(status_code=404, detail="Proof bundle not found")
    return proof
