"""Transaction routes — create, list, and retrieve."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.transaction import Transaction
from app.schemas.transaction import (
    TransactionCreate,
    TransactionListResponse,
    TransactionResponse,
)
from app.services.transaction_service import (
    create_transaction,
    get_transaction,
    list_transactions,
)

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/", response_model=EvaluationResponse, status_code=201)
def create_and_evaluate(
    payload: TransactionCreate,
    include_ows: bool = False,
    db: Session = Depends(get_db),
):
    """Create a transaction and immediately evaluate it against active policies.

    If ``include_ows`` is ``True`` the response will contain mocked Open Wallet
    Standard execution data (prepare, sign, wallet metadata).
    """
    tx = Transaction(**payload.model_dump())
    db.add(tx)
    db.commit()
    db.refresh(tx)

    result = evaluate_transaction(db, tx, include_ows=include_ows)
    return result
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
