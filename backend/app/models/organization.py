"""Organization ORM model — the real tenant registry.

An **Organization** is the actual, validated tenant boundary that every
``organization_id`` column across the canonical domain (see
``app.models._mixins.CanonicalMixin``) must reference. ``organization_id``
here is the natural primary key: it is never reassigned once created, and
being the primary key gives uniqueness without a separate constraint.

This table does not use ``CanonicalMixin`` — that mixin describes tenant-
*scoped* resources (things that belong to an organization); this table
describes the organizations themselves.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String

from app.core.database import Base
from app.utils.timestamps import utc_now


class Organization(Base):
    """Persistent, validated tenant record."""

    __tablename__ = "organizations"

    organization_id = Column(String, primary_key=True)
    organization_name = Column(String, nullable=False)
    status = Column(String, nullable=False, default="ACTIVE")

    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
