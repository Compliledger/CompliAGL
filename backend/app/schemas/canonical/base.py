"""Shared base classes for canonical response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CanonicalResponseBase(BaseModel):
    """Common read fields for every canonical first-class resource."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    organization_id: str
    schema_version: int
    created_at: datetime | None = None
    updated_at: datetime | None = None
