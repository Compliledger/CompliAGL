"""Transaction routes — create + evaluate."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.transaction import Transaction
from app.schemas.audit import AuditLogListResponse
from app.schemas.transaction import EvaluationResponse, TransactionCreate, TransactionResponse
from app.services import audit_service
from app.services.evaluation_service import evaluate_transaction
from app.api.routes.audit import build_audit_list_response

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post("/", response_model=EvaluationResponse, status_code=201)
def create_and_evaluate(payload: TransactionCreate, db: Session = Depends(get_db)):
    """Create a transaction and immediately evaluate it against active policies."""
    tx = Transaction(**payload.model_dump())
    db.add(tx)
    db.commit()
    db.refresh(tx)

    result = evaluate_transaction(db, tx)
    return result


@router.get("/", response_model=list[TransactionResponse])
def list_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Transaction).offset(skip).limit(limit).all()


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx


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
