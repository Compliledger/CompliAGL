"""CRUD service for Policy entities."""

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.policy import Policy
from app.schemas.policy import PolicyCreate, PolicyUpdate

# JSON array column names that need serialization/deserialization
_JSON_ARRAY_FIELDS = (
# JSON array fields stored as Text in SQLite
_JSON_FIELDS = (
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

def _serialize_json_fields(data: dict[str, Any]) -> dict[str, Any]:
    """Convert list values to JSON strings for storage."""
    for field in _JSON_FIELDS:
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


def _deserialize_json_field(value: Any) -> list[str]:
    """Parse a stored JSON string back to a list."""
    if isinstance(value, str):
        return json.loads(value)
    if isinstance(value, list):
        return value
    return []


def create_policy(db: Session, payload: PolicyCreate) -> Policy:
    data = _serialize_json_fields(payload.model_dump())
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


def get_policy_for_agent(db: Session, agent_id: str) -> Policy | None:
    """Return the active policy for a given agent (one active per agent)."""
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
    updates = _serialize_json_fields(payload.model_dump(exclude_unset=True))
    for key, value in updates.items():
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key in _JSON_ARRAY_FIELDS and value is not None:
            value = json.dumps(value)
        elif key in _JSON_LIST_FIELDS and value is not None:
            value = json.dumps(value)
        setattr(policy, key, value)
    db.commit()
    db.refresh(policy)
    return policy


def deactivate_policy(db: Session, policy_id: str) -> Policy | None:
    """Soft-delete: set the policy status to INACTIVE."""
    """Soft-delete: set status to INACTIVE."""
    policy = get_policy(db, policy_id)
    if not policy:
        return None
    policy.status = "INACTIVE"
    db.commit()
    db.refresh(policy)
    return policy


def delete_policy(db: Session, policy_id: str) -> bool:
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
    """Return a dict with JSON array fields deserialized.
    """Return a dict with parameters and JSON list fields deserialized.

    Used by both route handlers (full serialization) and the evaluation
    service (policy snapshot for the rule engine).
    """
    result = {
        "id": policy.id,
        "agent_id": policy.agent_id,
        "policy_name": policy.policy_name,
        "status": policy.status,
        "daily_budget": policy.daily_budget,
        "per_tx_limit": policy.per_tx_limit,
        "escalation_threshold": policy.escalation_threshold,
        "allowed_vendors": _deserialize_json_field(policy.allowed_vendors),
        "blocked_vendors": _deserialize_json_field(policy.blocked_vendors),
        "allowed_chains": _deserialize_json_field(policy.allowed_chains),
        "blocked_chains": _deserialize_json_field(policy.blocked_chains),
        "allowed_asset_symbols": _deserialize_json_field(policy.allowed_asset_symbols),
        "blocked_asset_symbols": _deserialize_json_field(policy.blocked_asset_symbols),
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
