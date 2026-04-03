"""CRUD service for Policy entities."""

import json

from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.schemas.policy import PolicyCreate, PolicyUpdate

# Fields stored as JSON-encoded lists in the database
_JSON_LIST_FIELDS = frozenset({
    "blocked_vendors",
    "blocked_chains",
    "blocked_asset_symbols",
    "allowed_vendors",
    "allowed_chains",
    "allowed_asset_symbols",
})


def _encode_json_lists(data: dict) -> dict:
    """Convert Python list values to JSON strings for JSON list columns."""
    for field in _JSON_LIST_FIELDS:
        if field in data and data[field] is not None:
            data[field] = json.dumps(data[field])
    return data


def _decode_json_list(raw) -> list[str] | None:
    """Decode a JSON-encoded list or return as-is."""
    if raw is None:
        return None
    if isinstance(raw, list):
        return raw
    try:
        parsed = json.loads(raw)
        return parsed if isinstance(parsed, list) else None
    except (json.JSONDecodeError, TypeError):
        return None


def create_policy(db: Session, payload: PolicyCreate) -> Policy:
    data = payload.model_dump()
    data["parameters"] = json.dumps(data["parameters"])
    data = _encode_json_lists(data)
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
        elif key in _JSON_LIST_FIELDS and value is not None:
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


def policy_to_dict(policy: Policy) -> dict:
    """Return a dict with parameters and JSON list fields deserialized.

    Used by both route handlers (full serialization) and the evaluation
    service (policy snapshot for the rule engine).
    """
    result = {
        "id": policy.id,
        "name": policy.name,
        "description": policy.description,
        "policy_type": policy.policy_type,
        "parameters": json.loads(policy.parameters) if isinstance(policy.parameters, str) else policy.parameters,
        "is_active": policy.is_active,
        "agent_id": policy.agent_id,
        "per_tx_limit": policy.per_tx_limit,
        "daily_budget": policy.daily_budget,
        "max_transactions_per_day": policy.max_transactions_per_day,
        "require_identity_check_above_amount": policy.require_identity_check_above_amount,
        "require_approval_above_threshold": policy.require_approval_above_threshold,
        "escalation_threshold": policy.escalation_threshold,
        "created_at": policy.created_at,
        "updated_at": policy.updated_at,
    }
    for field in _JSON_LIST_FIELDS:
        result[field] = _decode_json_list(getattr(policy, field, None))
    return result
