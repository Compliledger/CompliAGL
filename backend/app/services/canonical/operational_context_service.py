"""OperationalContext service."""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.operational_context import OperationalContext
from app.repositories.canonical import OperationalContextRepository
from app.schemas.canonical.operational_context import (
    OperationalContextCreate,
    OperationalContextUpdate,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now

# State fields stored as JSON text.
_STATE_FIELDS = (
    "risk_state",
    "account_state",
    "allowance_state",
    "merchant_state",
    "asset_state",
    "network_state",
    "operational_state_snapshot",
    "source_references",
)


def _dump(value: Any) -> Optional[str]:
    return json.dumps(value) if value is not None else None


def _compute_context_hash(organization_id: str, states: dict[str, Any]) -> str:
    payload = {"organization_id": organization_id, **states}
    return hash_dict(payload)


def create(db: Session, payload: OperationalContextCreate) -> OperationalContext:
    states = {field: getattr(payload, field) for field in _STATE_FIELDS}
    obj = OperationalContext(
        organization_id=payload.organization_id,
        business_unit=payload.business_unit,
        jurisdiction=payload.jurisdiction,
        environment=payload.environment.value,
        context_timestamp=payload.context_timestamp or utc_now(),
        context_hash=_compute_context_hash(payload.organization_id, states),
        **{field: _dump(states[field]) for field in _STATE_FIELDS},
    )
    return OperationalContextRepository(db).add(obj)


def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[OperationalContext]:
    return OperationalContextRepository(db).get(organization_id, resource_id)


def list_(
    db: Session, organization_id: str, *, skip: int = 0, limit: int = 100
) -> Sequence[OperationalContext]:
    return OperationalContextRepository(db).list(
        organization_id, skip=skip, limit=limit
    )


def update(
    db: Session,
    organization_id: str,
    resource_id: str,
    payload: OperationalContextUpdate,
) -> Optional[OperationalContext]:
    repo = OperationalContextRepository(db)
    obj = repo.get(organization_id, resource_id)
    if obj is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    for field in _STATE_FIELDS:
        if field in data:
            setattr(obj, field, _dump(data[field]))
    # Recompute the context hash from the (possibly updated) state snapshot.
    states = {
        field: (json.loads(getattr(obj, field)) if getattr(obj, field) else None)
        for field in _STATE_FIELDS
    }
    obj.context_hash = _compute_context_hash(organization_id, states)
    return repo.save(obj)
