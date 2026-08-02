"""Intent service — integrity hashing, idempotency, and lifecycle transitions."""

from __future__ import annotations

import json
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.intent import Intent
from app.repositories.canonical import IntentRepository
from app.schemas.canonical.intent import IntentCreate, IntentUpdate
from app.services.canonical.transitions import (
    INTENT_TRANSITIONS,
    validate_transition,
)
from app.utils.canonical_enums import IntentStatus
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now


def _compute_integrity_hash(payload: IntentCreate) -> str:
    """Deterministic hash binding the semantic content of an intent."""
    canonical = {
        "organization_id": payload.organization_id,
        "intent_type": payload.intent_type.value,
        "action": payload.action,
        "requested_outcome": payload.requested_outcome,
        "actor_id": payload.actor_id,
        "originating_application": payload.originating_application,
        "parameters": payload.parameters,
        "amount_minor": payload.amount_minor,
        "amount_currency": payload.amount_currency,
        "correlation_id": payload.correlation_id,
        "version": payload.version,
    }
    return hash_dict(canonical)


def create(db: Session, payload: IntentCreate) -> Intent:
    """Create an intent.

    Idempotent on ``(organization_id, idempotency_key)``: when a key is supplied
    and an intent already exists for it, the existing intent is returned instead
    of creating a duplicate.
    """
    repo = IntentRepository(db)
    if payload.idempotency_key:
        existing = repo.find_one(
            payload.organization_id, idempotency_key=payload.idempotency_key
        )
        if existing is not None:
            return existing

    obj = Intent(
        organization_id=payload.organization_id,
        intent_type=payload.intent_type.value,
        action=payload.action,
        requested_outcome=payload.requested_outcome,
        actor_id=payload.actor_id,
        originating_application=payload.originating_application,
        parameters=(
            json.dumps(payload.parameters) if payload.parameters is not None else None
        ),
        amount_minor=payload.amount_minor,
        amount_currency=payload.amount_currency,
        correlation_id=payload.correlation_id,
        idempotency_key=payload.idempotency_key,
        submitted_at=utc_now(),
        expires_at=payload.expires_at,
        version=payload.version,
        integrity_hash=_compute_integrity_hash(payload),
        status=IntentStatus.SUBMITTED.value,
    )
    return repo.add(obj)


def get(db: Session, organization_id: str, resource_id: str) -> Optional[Intent]:
    return IntentRepository(db).get(organization_id, resource_id)


def list_(
    db: Session, organization_id: str, *, skip: int = 0, limit: int = 100
) -> Sequence[Intent]:
    return IntentRepository(db).list(organization_id, skip=skip, limit=limit)


def update(
    db: Session, organization_id: str, resource_id: str, payload: IntentUpdate
) -> Optional[Intent]:
    repo = IntentRepository(db)
    obj = repo.get(organization_id, resource_id)
    if obj is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    if "parameters" in data:
        value = data.pop("parameters")
        obj.parameters = json.dumps(value) if value is not None else None
    for key, value in data.items():
        setattr(obj, key, value)
    return repo.save(obj)


def transition_status(
    db: Session, organization_id: str, resource_id: str, new_status: IntentStatus
) -> Optional[Intent]:
    """Move an intent to ``new_status``, enforcing the lifecycle state machine."""
    repo = IntentRepository(db)
    obj = repo.get(organization_id, resource_id)
    if obj is None:
        return None
    validate_transition(
        "Intent", INTENT_TRANSITIONS, obj.status, new_status.value
    )
    obj.status = new_status.value
    return repo.save(obj)
