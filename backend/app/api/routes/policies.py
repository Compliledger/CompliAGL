"""Policy CRUD routes."""

import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.policy import PolicyCreate, PolicyResponse, PolicyUpdate
from app.services import policy_service

router = APIRouter(prefix="/policies", tags=["policies"])


def _serialise_policy(policy) -> dict:
    """Convert a Policy ORM instance to a dict with parsed parameters."""
    data = {
        "id": policy.id,
        "name": policy.name,
        "description": policy.description,
        "policy_type": policy.policy_type,
        "parameters": json.loads(policy.parameters) if isinstance(policy.parameters, str) else policy.parameters,
        "is_active": policy.is_active,
        "created_at": policy.created_at,
        "updated_at": policy.updated_at,
    }
    return data


@router.post("/", response_model=PolicyResponse, status_code=201)
def create_policy(payload: PolicyCreate, db: Session = Depends(get_db)):
    policy = policy_service.create_policy(db, payload)
    return _serialise_policy(policy)


@router.get("/", response_model=list[PolicyResponse])
def list_policies(skip: int = 0, limit: int = 100, active_only: bool = False, db: Session = Depends(get_db)):
    policies = policy_service.list_policies(db, skip=skip, limit=limit, active_only=active_only)
    return [_serialise_policy(p) for p in policies]


@router.get("/{policy_id}", response_model=PolicyResponse)
def get_policy(policy_id: str, db: Session = Depends(get_db)):
    policy = policy_service.get_policy(db, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _serialise_policy(policy)


@router.patch("/{policy_id}", response_model=PolicyResponse)
def update_policy(policy_id: str, payload: PolicyUpdate, db: Session = Depends(get_db)):
    policy = policy_service.update_policy(db, policy_id, payload)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return _serialise_policy(policy)


@router.delete("/{policy_id}")
def delete_policy(policy_id: str, db: Session = Depends(get_db)):
    if not policy_service.delete_policy(db, policy_id):
        raise HTTPException(status_code=404, detail="Policy not found")
    return {"detail": "Policy deleted"}
