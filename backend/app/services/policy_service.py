"""CRUD service for Policy entities."""

import json

from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.schemas.policy import PolicyCreate, PolicyUpdate

# JSON array column names that need serialization/deserialization
_JSON_ARRAY_FIELDS = (
    "allowed_vendors",
    "blocked_vendors",
    "allowed_chains",
    "blocked_chains",
    "allowed_asset_symbols",
    "blocked_asset_symbols",
)


def create_policy(db: Session, payload: PolicyCreate) -> Policy:
    data = payload.model_dump()
    for field in _JSON_ARRAY_FIELDS:
        data[field] = json.dumps(data[field])
    policy = Policy(**data)
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def get_policy(db: Session, policy_id: str) -> Policy | None:
    return db.query(Policy).filter(Policy.id == policy_id).first()


def get_policy_for_agent(db: Session, agent_id: str) -> Policy | None:
    """Return the active policy for a given agent (one active per agent)."""
    return (
        db.query(Policy)
        .filter(Policy.agent_id == agent_id, Policy.status == "ACTIVE")
        .first()
    )


def list_policies(db: Session, skip: int = 0, limit: int = 100, active_only: bool = False) -> list[Policy]:
    query = db.query(Policy)
    if active_only:
        query = query.filter(Policy.status == "ACTIVE")
    return query.offset(skip).limit(limit).all()


def update_policy(db: Session, policy_id: str, payload: PolicyUpdate) -> Policy | None:
    policy = get_policy(db, policy_id)
    if not policy:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in _JSON_ARRAY_FIELDS and value is not None:
            value = json.dumps(value)
        setattr(policy, key, value)
    db.commit()
    db.refresh(policy)
    return policy


def deactivate_policy(db: Session, policy_id: str) -> Policy | None:
    """Soft-delete: set the policy status to INACTIVE."""
    policy = get_policy(db, policy_id)
    if not policy:
        return None
    policy.status = "INACTIVE"
    db.commit()
    db.refresh(policy)
    return policy


def policy_to_dict(policy: Policy) -> dict:
    """Return a dict with JSON array fields deserialized from JSON strings."""
    data = {
        "id": policy.id,
        "agent_id": policy.agent_id,
        "policy_name": policy.policy_name,
        "status": policy.status,
        "daily_budget": policy.daily_budget,
        "per_tx_limit": policy.per_tx_limit,
        "escalation_threshold": policy.escalation_threshold,
        "require_approval_above_threshold": policy.require_approval_above_threshold,
        "require_identity_check_above_amount": policy.require_identity_check_above_amount,
        "max_transactions_per_day": policy.max_transactions_per_day,
        "timezone": policy.timezone,
        "rule_version": policy.rule_version,
        "created_at": policy.created_at,
        "updated_at": policy.updated_at,
    }
    for field in _JSON_ARRAY_FIELDS:
        raw = getattr(policy, field)
        data[field] = json.loads(raw) if isinstance(raw, str) else raw
    return data
