"""CRUD service for Policy entities."""

import json

from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.schemas.policy import PolicyCreate, PolicyUpdate


def create_policy(db: Session, payload: PolicyCreate) -> Policy:
    data = payload.model_dump()
    data["parameters"] = json.dumps(data["parameters"])
    policy = Policy(**data)
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def get_policy(db: Session, policy_id: str) -> Policy | None:
    return db.query(Policy).filter(Policy.id == policy_id).first()


def list_policies(db: Session, skip: int = 0, limit: int = 100, active_only: bool = False) -> list[Policy]:
    query = db.query(Policy)
    if active_only:
        query = query.filter(Policy.is_active.is_(True))
    return query.offset(skip).limit(limit).all()


def update_policy(db: Session, policy_id: str, payload: PolicyUpdate) -> Policy | None:
    policy = get_policy(db, policy_id)
    if not policy:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "parameters" and value is not None:
            value = json.dumps(value)
        setattr(policy, key, value)
    db.commit()
    db.refresh(policy)
    return policy


def delete_policy(db: Session, policy_id: str) -> bool:
    policy = get_policy(db, policy_id)
    if not policy:
        return False
    db.delete(policy)
    db.commit()
    return True


def _parse_policy(policy: Policy) -> dict:
    """Return a dict with parameters deserialized from JSON."""
    return {
        "id": policy.id,
        "name": policy.name,
        "policy_type": policy.policy_type,
        "parameters": json.loads(policy.parameters) if isinstance(policy.parameters, str) else policy.parameters,
        "is_active": policy.is_active,
    }
