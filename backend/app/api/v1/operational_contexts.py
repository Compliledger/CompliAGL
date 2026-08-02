"""OperationalContext v1 routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.schemas.canonical.operational_context import (
    OperationalContextCreate,
    OperationalContextResponse,
    OperationalContextUpdate,
)
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical import operational_context_service as svc

router = APIRouter(prefix="/operational-contexts", tags=["v1:operational-contexts"])


@router.post("", response_model=OperationalContextResponse, status_code=201)
def create_operational_context(
    payload: OperationalContextCreate, db: Session = Depends(get_db)
):
    return orm_to_dict(svc.create(db, payload))


@router.get("", response_model=list[OperationalContextResponse])
def list_operational_contexts(
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [orm_to_dict(o) for o in svc.list_(db, organization_id, skip=skip, limit=limit)]


@router.get("/{resource_id}", response_model=OperationalContextResponse)
def get_operational_context(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.get(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="OperationalContext not found")
    return orm_to_dict(obj)


@router.patch("/{resource_id}", response_model=OperationalContextResponse)
def update_operational_context(
    resource_id: str,
    payload: OperationalContextUpdate,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.update(db, organization_id, resource_id, payload)
    if obj is None:
        raise HTTPException(status_code=404, detail="OperationalContext not found")
    return orm_to_dict(obj)
