"""Canonical AIProof v1 API.

Exposes the single canonical AIProof: generate + sign, retrieve, verify locally,
submit to CompliLedger, retrieve handoff status, and retrieve AIProof history.
Also publishes the versioned AIProof JSON Schema.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.schemas.canonical.aiproof import (
    AIProof,
    AIProofGenerateRequest,
    AIProofHandoffStatusResponse,
    AIProofHistoryItem,
    AIProofSubmitRequest,
    AIProofSubmitResponse,
)
from app.services.canonical.aiproof import generator, json_schema
from app.services.canonical.aiproof import service as svc
from app.services.canonical.aiproof.verify import AIProofVerification

router = APIRouter(prefix="/aiproofs", tags=["v1:aiproofs"])


@router.get("/schema")
def get_aiproof_schema() -> dict:
    """Return the published, versioned AIProof JSON Schema."""
    return json_schema.aiproof_json_schema()


@router.post("", response_model=AIProof, status_code=201)
def generate_aiproof(
    payload: AIProofGenerateRequest, db: Session = Depends(get_db)
) -> AIProof:
    """Generate, sign and persist a canonical AIProof for a governed outcome."""
    content = payload.model_dump(exclude={"requested_proof_policy", "privacy_classification"})
    proof = generator.generate_signed_aiproof(**content)
    svc.store_aiproof(db, proof)
    return proof


@router.get("/history", response_model=list[AIProofHistoryItem])
def get_aiproof_history(
    intent_id: str | None = None,
    actor_identity_id: str | None = None,
    governance_evaluation_id: str | None = None,
    correlation_id: str | None = None,
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
) -> list[AIProofHistoryItem]:
    """Return the AIProof history for the tenant, filtered by lifecycle refs."""
    rows = svc.list_history(
        db,
        organization_id,
        intent_id=intent_id,
        actor_identity_id=actor_identity_id,
        governance_evaluation_id=governance_evaluation_id,
        correlation_id=correlation_id,
        skip=skip,
        limit=limit,
    )
    return [AIProofHistoryItem.model_validate(row) for row in rows]


@router.get("/{aiproof_id}", response_model=AIProof)
def retrieve_aiproof(
    aiproof_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
) -> AIProof:
    """Retrieve a stored canonical AIProof."""
    proof = svc.get_aiproof(db, organization_id, aiproof_id)
    if proof is None:
        raise HTTPException(status_code=404, detail=f"AIProof not found: {aiproof_id}")
    return proof


@router.post("/{aiproof_id}/verify", response_model=AIProofVerification)
def verify_aiproof_endpoint(
    aiproof_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
) -> AIProofVerification:
    """Independently schema-validate + signature-verify a stored AIProof."""
    result = svc.verify_local(db, organization_id, aiproof_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"AIProof not found: {aiproof_id}")
    return result


@router.post("/{aiproof_id}/submit", response_model=AIProofSubmitResponse)
def submit_aiproof(
    aiproof_id: str,
    payload: AIProofSubmitRequest | None = None,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
) -> AIProofSubmitResponse:
    """Submit a stored AIProof to CompliLedger via the formal handoff."""
    payload = payload or AIProofSubmitRequest()
    try:
        outcome = svc.submit_to_compliledger(
            db,
            organization_id,
            aiproof_id,
            requested_proof_policy=payload.requested_proof_policy,
            privacy_classification=payload.privacy_classification,
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if outcome is None:
        raise HTTPException(status_code=404, detail=f"AIProof not found: {aiproof_id}")
    _row, handoff_payload, result = outcome
    return AIProofSubmitResponse(
        handoff=handoff_payload,
        result_status=result.status.value,
        handoff_reference=result.reference,
        detail=result.detail,
    )


@router.get("/{aiproof_id}/handoff", response_model=AIProofHandoffStatusResponse)
def aiproof_handoff_status(
    aiproof_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
) -> AIProofHandoffStatusResponse:
    """Retrieve the CompliLedger handoff status for a stored AIProof."""
    status = svc.get_handoff_status(db, organization_id, aiproof_id)
    if status is None:
        raise HTTPException(status_code=404, detail=f"AIProof not found: {aiproof_id}")
    return AIProofHandoffStatusResponse.model_validate(status)
