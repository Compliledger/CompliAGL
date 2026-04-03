"""CRUD service for Transaction entities."""

import json

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.transaction import Transaction
from app.schemas.transaction import TransactionCreate
from app.utils.enums import TransactionStatus


def create_transaction(db: Session, payload: TransactionCreate) -> Transaction:
    """Create a new transaction, copying wallet_address from the agent."""
    agent = db.query(Agent).filter(Agent.id == payload.agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if not agent.wallet_address:
        raise HTTPException(
            status_code=422, detail="Agent does not have a wallet address"
        )

    tx = Transaction(
        agent_id=payload.agent_id,
        wallet_address=agent.wallet_address,
        vendor=payload.vendor,
        chain=payload.chain,
        asset_symbol=payload.asset_symbol,
        amount=payload.amount,
        destination=payload.destination,
        memo=payload.memo,
        metadata_json=json.dumps(payload.metadata_json),
        status=TransactionStatus.SUBMITTED.value,
    )
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def get_transaction(db: Session, transaction_id: str) -> Transaction | None:
    """Retrieve a single transaction by ID."""
    return db.query(Transaction).filter(Transaction.id == transaction_id).first()


def list_transactions(
    db: Session, skip: int = 0, limit: int = 100
) -> list[Transaction]:
    """Return a paginated list of transactions."""
    return db.query(Transaction).offset(skip).limit(limit).all()
