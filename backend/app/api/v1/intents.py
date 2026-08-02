"""Intent v1 routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.v1.deps import get_org_id
from app.core.database import get_db
from app.schemas.canonical.intent import (
    IntentCreate,
    IntentResponse,
    IntentStatusUpdate,
    IntentUpdate,
)
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical import intent_service as svc
from app.services.canonical.errors import InvalidTransitionError

router = APIRouter(prefix="/intents", tags=["v1:intents"])


@router.post("", response_model=IntentResponse, status_code=201)
def create_intent(payload: IntentCreate, db: Session = Depends(get_db)):
    return orm_to_dict(svc.create(db, payload))


@router.get("", response_model=list[IntentResponse])
def list_intents(
    skip: int = 0,
    limit: int = 100,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    return [orm_to_dict(o) for o in svc.list_(db, organization_id, skip=skip, limit=limit)]


@router.get("/{resource_id}", response_model=IntentResponse)
def get_intent(
    resource_id: str,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.get(db, organization_id, resource_id)
    if obj is None:
        raise HTTPException(status_code=404, detail="Intent not found")
    return orm_to_dict(obj)


@router.patch("/{resource_id}", response_model=IntentResponse)
def update_intent(
    resource_id: str,
    payload: IntentUpdate,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    obj = svc.update(db, organization_id, resource_id, payload)
    if obj is None:
        raise HTTPException(status_code=404, detail="Intent not found")
    return orm_to_dict(obj)


@router.post("/{resource_id}/transition", response_model=IntentResponse)
def transition_intent(
    resource_id: str,
    payload: IntentStatusUpdate,
    organization_id: str = Depends(get_org_id),
    db: Session = Depends(get_db),
):
    try:
        obj = svc.transition_status(db, organization_id, resource_id, payload.status)
    except InvalidTransitionError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    if obj is None:
        raise HTTPException(status_code=404, detail="Intent not found")
    return orm_to_dict(obj)
