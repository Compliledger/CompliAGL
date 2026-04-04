"""Transaction routes — create, evaluate, list, and retrieve."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.transaction import Transaction
from app.schemas.audit import AuditLogListResponse
from app.schemas.proof_bundle import ProofBundleResponse
from app.schemas.transaction import (
    EvaluationResponse,
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
)
from app.services import audit_service, proof_service
from app.services.evaluation_service import evaluate_transaction
from app.services.transaction_service import (
    create_transaction,
    get_transaction,
    list_transactions,
)
from app.api.routes.audit import build_audit_list_response

router = APIRouter(prefix="/transactions", tags=["transactions"])


def _tx_to_response(tx) -> dict:
    """Convert a Transaction ORM instance to a response-ready dict."""
    data = {
        "id": tx.id,
        "agent_id": tx.agent_id,
        "wallet_address": tx.wallet_address,
        "vendor": tx.vendor,
        "chain": tx.chain,
        "asset_symbol": tx.asset_symbol,
        "amount": tx.amount,
        "destination": tx.destination,
        "memo": tx.memo,
        "status": tx.status,
        "decision_result": tx.decision_result,
        "decision_reason_summary": tx.decision_reason_summary,
        "submitted_at": tx.submitted_at,
        "evaluated_at": tx.evaluated_at,
        "executed_at": tx.executed_at,
        "created_at": tx.created_at,
        "updated_at": tx.updated_at,
    }
    # Deserialize metadata_json from stored JSON string to dict
    raw = tx.metadata_json or "{}"
    try:
        data["metadata_json"] = json.loads(raw) if isinstance(raw, str) else raw
    except (json.JSONDecodeError, TypeError):
        data["metadata_json"] = {}
    return data


@router.post("/", response_model=TransactionResponse, status_code=201)
def create(payload: TransactionCreate, db: Session = Depends(get_db)):
    """Create a new transaction with status SUBMITTED."""
    tx = create_transaction(db, payload)
    return _tx_to_response(tx)


@router.post("/{transaction_id}/evaluate", response_model=EvaluationResponse)
def evaluate_existing_transaction(transaction_id: str, db: Session = Depends(get_db)):
    """Evaluate a submitted transaction against the agent's active policy."""
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    if tx.status not in ("SUBMITTED", "PENDING"):
        raise HTTPException(
            status_code=400,
            detail=f"Transaction is in '{tx.status}' state and cannot be re-evaluated",
        )
    result = evaluate_transaction(db, transaction_id)
    return result


@router.get("/", response_model=TransactionListResponse)
def list_all(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """Return a paginated list of transactions."""
    total = db.query(Transaction).count()
    txs = list_transactions(db, skip=skip, limit=limit)
    items = [_tx_to_response(tx) for tx in txs]
    return TransactionListResponse(items=items, count=total)


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_by_id(transaction_id: str, db: Session = Depends(get_db)):
    """Retrieve a single transaction by its ID."""
    tx = get_transaction(db, transaction_id)
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return _tx_to_response(tx)


@router.get("/{transaction_id}/proof", response_model=ProofBundleResponse)
def get_transaction_proof(transaction_id: str, db: Session = Depends(get_db)):
    """Return the proof bundle associated with a transaction."""
    proof = proof_service.get_proof_by_transaction(db, transaction_id)
    if not proof:
        raise HTTPException(status_code=404, detail="Proof bundle not found for this transaction")
    return proof


@router.get(
    "/{transaction_id}/audit",
    response_model=AuditLogListResponse,
    tags=["audit"],
)
def list_transaction_audit_logs(
    transaction_id: str,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """Return audit log entries for a specific transaction, newest first."""
    logs = audit_service.list_audit_logs_for_transaction(
        db, transaction_id, skip=skip, limit=limit
    )
    return build_audit_list_response(logs)
