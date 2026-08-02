"""ActorIdentity service."""

from __future__ import annotations

import json
from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.actor_identity import ActorIdentity
from app.repositories.canonical import ActorIdentityRepository
from app.schemas.canonical.actor_identity import (
    ActorIdentityCreate,
    ActorIdentityUpdate,
)


def create(db: Session, payload: ActorIdentityCreate) -> ActorIdentity:
    obj = ActorIdentity(
        organization_id=payload.organization_id,
        actor_type=payload.actor_type.value,
        human_principal_id=payload.human_principal_id,
        external_account_id=payload.external_account_id,
        wallet_or_agent_account_id=payload.wallet_or_agent_account_id,
        credential_type=payload.credential_type.value,
        credential_issuer=payload.credential_issuer,
        credential_reference=payload.credential_reference,
        verification_status=payload.verification_status.value,
        valid_from=payload.valid_from,
        expires_at=payload.expires_at,
        revocation_status=payload.revocation_status.value,
        identity_metadata=(
            json.dumps(payload.identity_metadata)
            if payload.identity_metadata is not None
            else None
        ),
    )
    return ActorIdentityRepository(db).add(obj)


def get(db: Session, organization_id: str, resource_id: str) -> Optional[ActorIdentity]:
    return ActorIdentityRepository(db).get(organization_id, resource_id)


def list_(
    db: Session, organization_id: str, *, skip: int = 0, limit: int = 100
) -> Sequence[ActorIdentity]:
    return ActorIdentityRepository(db).list(organization_id, skip=skip, limit=limit)


def update(
    db: Session,
    organization_id: str,
    resource_id: str,
    payload: ActorIdentityUpdate,
) -> Optional[ActorIdentity]:
    repo = ActorIdentityRepository(db)
    obj = repo.get(organization_id, resource_id)
    if obj is None:
        return None
    data = payload.model_dump(exclude_unset=True)
    if "verification_status" in data and data["verification_status"] is not None:
        obj.verification_status = data.pop("verification_status").value
    if "revocation_status" in data and data["revocation_status"] is not None:
        obj.revocation_status = data.pop("revocation_status").value
    if "identity_metadata" in data:
        value = data.pop("identity_metadata")
        obj.identity_metadata = json.dumps(value) if value is not None else None
    for key, value in data.items():
        setattr(obj, key, value)
    return repo.save(obj)
