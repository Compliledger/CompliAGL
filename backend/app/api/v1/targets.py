"""Target v1 routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.schemas.canonical.serialization import orm_to_dict
from app.schemas.canonical.target import (
    TargetCreate,
    TargetResponse,
    TargetUpdate,
)
from app.services.canonical import target_service as svc

router = APIRouter(prefix="/targets", tags=["v1:targets"])


@router.post("", response_model=TargetResponse, status_code=201)
def create_target(payload: TargetCreate, db: Session = Depends(get_db)):
    return orm_to_dict(svc.create(db, payload))


@router.get("", response_model=list[TargetResponse])
def list_targets(
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [orm_to_dict(o) for o in svc.list_(db, organization_id, skip=skip, limit=limit)]


@router.get("/{resource_id}", response_model=TargetResponse)
def get_target(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.get(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Target not found")
    return orm_to_dict(obj)


@router.patch("/{resource_id}", response_model=TargetResponse)
def update_target(
    resource_id: str,
    payload: TargetUpdate,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.update(db, organization_id, resource_id, payload)
    if obj is None:
        raise HTTPException(status_code=404, detail="Target not found")
    return orm_to_dict(obj)
