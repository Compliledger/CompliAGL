"""ActorIdentity v1 routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.schemas.canonical.actor_identity import (
    ActorIdentityCreate,
    ActorIdentityResponse,
    ActorIdentityUpdate,
)
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical import actor_identity_service as svc

router = APIRouter(prefix="/actor-identities", tags=["v1:actor-identities"])


@router.post("", response_model=ActorIdentityResponse, status_code=201)
def create_actor_identity(payload: ActorIdentityCreate, db: Session = Depends(get_db)):
    obj = svc.create(db, payload)
    return orm_to_dict(obj)


@router.get("", response_model=list[ActorIdentityResponse])
def list_actor_identities(
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [orm_to_dict(o) for o in svc.list_(db, organization_id, skip=skip, limit=limit)]


@router.get("/{resource_id}", response_model=ActorIdentityResponse)
def get_actor_identity(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.get(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="ActorIdentity not found")
    return orm_to_dict(obj)


@router.patch("/{resource_id}", response_model=ActorIdentityResponse)
def update_actor_identity(
    resource_id: str,
    payload: ActorIdentityUpdate,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.update(db, organization_id, resource_id, payload)
    if obj is None:
        raise HTTPException(status_code=404, detail="ActorIdentity not found")
    return orm_to_dict(obj)
