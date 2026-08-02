"""Shared SQLAlchemy mixins for canonical first-class domain models.

Every canonical resource carries:

* an **immutable** primary identifier (``id`` — never exposed in update
  schemas and never mutated by services),
* ``organization_id`` for tenant isolation (enforced on every repository query),
* ``schema_version`` for forward-compatible serialization,
* ``created_at`` / ``updated_at`` audit timestamps.
"""

from __future__ import annotations

import uuid

from sqlalchemy import Column, DateTime, Integer, String, func
from sqlalchemy.orm import declarative_mixin

# Current schema version for canonical domain objects. Bumped when the on-disk
# shape of a canonical resource changes in a breaking way.
CANONICAL_SCHEMA_VERSION = 1


@declarative_mixin
class CanonicalMixin:
    """Common columns for canonical, tenant-scoped, versioned resources."""

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    organization_id = Column(String, nullable=False, index=True)
    schema_version = Column(
        Integer, nullable=False, default=CANONICAL_SCHEMA_VERSION
    )
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
