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

from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.orm import declarative_mixin

from app.utils.timestamps import utc_now

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
    # Python-side (not server_default=func.now()) so timestamps carry
    # microsecond resolution on every backend, SQLite included. SQLite's
    # CURRENT_TIMESTAMP truncates to whole seconds, which let two records
    # created in the same second tie under the repositories' ubiquitous
    # `ORDER BY created_at DESC LIMIT 1` "latest" queries, with no defined
    # tiebreaker -- non-deterministically returning a stale row instead of
    # the actual latest one.
    created_at = Column(DateTime(timezone=True), default=utc_now, nullable=False)
    updated_at = Column(
        DateTime(timezone=True),
        default=utc_now,
        onupdate=utc_now,
        nullable=False,
    )
