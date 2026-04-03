"""Transaction routes — create + evaluate."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.transaction import Transaction
from app.schemas.transaction import EvaluationResponse, TransactionCreate, TransactionResponse
from app.services.evaluation_service import evaluate_transaction

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


@router.get("/", response_model=list[TransactionResponse])
def list_transactions(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    return db.query(Transaction).offset(skip).limit(limit).all()


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(transaction_id: str, db: Session = Depends(get_db)):
    tx = db.query(Transaction).filter(Transaction.id == transaction_id).first()
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return tx
