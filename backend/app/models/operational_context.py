"""OperationalContext ORM model — canonical first-class resource.

The **OperationalContext** is the current operational state at the moment an
intent is governed. It is no longer stored only in generic metadata: risk,
account, allowance, merchant, asset, and network state are explicit, and a
deterministic ``context_hash`` binds the snapshot.

State snapshots are stored as JSON text. Any monetary values embedded in those
snapshots must use integer minor units — floating-point types are never used
for governed monetary values.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import EnvironmentType


class OperationalContext(CanonicalMixin, Base):
    """Persistent snapshot of current operational state."""

    __tablename__ = "operational_contexts"

    business_unit = Column(String, nullable=True)
    jurisdiction = Column(String, nullable=True)
    environment = Column(
        String, nullable=False, default=EnvironmentType.PRODUCTION.value
    )
    context_timestamp = Column(DateTime(timezone=True), nullable=True)

    # --- Explicit state snapshots (JSON text) ---
    risk_state = Column(Text, nullable=True)
    account_state = Column(Text, nullable=True)
    allowance_state = Column(Text, nullable=True)
    merchant_state = Column(Text, nullable=True)
    asset_state = Column(Text, nullable=True)
    network_state = Column(Text, nullable=True)

    # Combined current operational-state snapshot + provenance references.
    operational_state_snapshot = Column(Text, nullable=True)
    source_references = Column(Text, nullable=True)

    context_hash = Column(String, nullable=True, index=True)
