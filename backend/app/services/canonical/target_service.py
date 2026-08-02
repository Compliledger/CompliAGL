"""Target service."""

from __future__ import annotations

import json
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.target import Target
from app.repositories.canonical import TargetRepository
from app.schemas.canonical.target import TargetCreate, TargetUpdate


def create(db: Session, payload: TargetCreate) -> Target:
    obj = Target(
        organization_id=payload.organization_id,
        target_type=payload.target_type.value,
        external_identifier=payload.external_identifier,
        owner=payload.owner,
        organization=payload.organization,
        classification=payload.classification,
        trust_status=payload.trust_status.value,
        network_or_environment=payload.network_or_environment,
        target_metadata=(
            json.dumps(payload.target_metadata)
            if payload.target_metadata is not None
            else None
        ),
    )
    return TargetRepository(db).add(obj)


def get(db: Session, organization_id: str, resource_id: str) -> Optional[Target]:
    return TargetRepository(db).get(organization_id, resource_id)


def list_(
    db: Session, organization_id: str, *, skip: int = 0, limit: int = 100
) -> Sequence[Target]:
    return TargetRepository(db).list(organization_id, skip=skip, limit=limit)


def update(
    db: Session, organization_id: str, resource_id: str, payload: TargetUpdate
) -> Optional[Target]:
    repo = TargetRepository(db)
    obj = repo.get(organization_id, resource_id)
    if obj is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    if "trust_status" in data and data["trust_status"] is not None:
        obj.trust_status = data.pop("trust_status").value
    if "target_metadata" in data:
        value = data.pop("target_metadata")
        obj.target_metadata = json.dumps(value) if value is not None else None
    for key, value in data.items():
        setattr(obj, key, value)
    return repo.save(obj)
