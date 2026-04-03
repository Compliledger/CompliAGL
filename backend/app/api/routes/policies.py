"""Policy CRUD routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.policy import PolicyCreate, PolicyResponse, PolicyUpdate
from app.services import policy_service
from app.services.policy_service import policy_to_dict

router = APIRouter(prefix="/policies", tags=["policies"])


@router.post("/", response_model=PolicyResponse, status_code=201)
def create_policy(payload: PolicyCreate, db: Session = Depends(get_db)):
    policy = policy_service.create_policy(db, payload)
    return policy_to_dict(policy)


@router.get("/", response_model=list[PolicyResponse])
def list_policies(skip: int = 0, limit: int = 100, active_only: bool = False, db: Session = Depends(get_db)):
    policies = policy_service.list_policies(db, skip=skip, limit=limit, active_only=active_only)
    return [policy_to_dict(p) for p in policies]


@router.get("/{policy_id}", response_model=PolicyResponse)
def get_policy(policy_id: str, db: Session = Depends(get_db)):
    policy = policy_service.get_policy(db, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy_to_dict(policy)


@router.patch("/{policy_id}", response_model=PolicyResponse)
def update_policy(policy_id: str, payload: PolicyUpdate, db: Session = Depends(get_db)):
    policy = policy_service.update_policy(db, policy_id, payload)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy_to_dict(policy)


@router.delete("/{policy_id}", response_model=PolicyResponse)
def deactivate_policy(policy_id: str, db: Session = Depends(get_db)):
    policy = policy_service.deactivate_policy(db, policy_id)
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    return policy_to_dict(policy)
