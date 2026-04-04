"""CRUD service for Policy entities."""

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.schemas.policy import PolicyCreate, PolicyUpdate

# JSON array fields stored as Text in SQLite
_JSON_LIST_FIELDS = frozenset({
    "allowed_vendors",
    "blocked_vendors",
    "allowed_chains",
    "blocked_chains",
    "allowed_asset_symbols",
    "blocked_asset_symbols",
})


def _encode_json_lists(data: dict) -> dict:
    """Convert Python list values to JSON strings for JSON list columns."""
    for field in _JSON_LIST_FIELDS:
        if field in data and data[field] is not None:
            data[field] = json.dumps(data[field])
    return data


def _decode_json_list(raw: Any) -> list[str] | None:
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
    data = _encode_json_lists(data)
    policy = Policy(**data)
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def get_policy(db: Session, policy_id: str) -> Policy | None:
    return db.query(Policy).filter(Policy.id == policy_id).first()


def get_policy_for_agent(db: Session, agent_id: str) -> Policy | None:
    """Return the active policy for the given agent (one active per agent)."""
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
        if key in _JSON_LIST_FIELDS and value is not None:
            value = json.dumps(value)
        setattr(policy, key, value)
    db.commit()
    db.refresh(policy)
    return policy


def deactivate_policy(db: Session, policy_id: str) -> Policy | None:
    """Soft-delete: set status to INACTIVE."""
    policy = get_policy(db, policy_id)
    if not policy:
        return None
    policy.status = "INACTIVE"
    db.commit()
    db.refresh(policy)
    return policy


def policy_to_dict(policy: Policy) -> dict:
    """Return a dict with JSON list fields deserialized."""
    result = {
        "id": policy.id,
        "agent_id": policy.agent_id,
        "policy_name": policy.policy_name,
        "name": policy.name,
        "description": policy.description,
        "policy_type": policy.policy_type,
        "status": policy.status,
        "is_active": policy.is_active,
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
    # Deserialize JSON list fields
    for field in _JSON_LIST_FIELDS:
        result[field] = _decode_json_list(getattr(policy, field, None))
    # Deserialize parameters JSON
    try:
        result["parameters"] = json.loads(policy.parameters) if isinstance(policy.parameters, str) else (policy.parameters or {})
    except (json.JSONDecodeError, TypeError):
        result["parameters"] = {}
    return result
