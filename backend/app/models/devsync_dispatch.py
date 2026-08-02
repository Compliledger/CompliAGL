"""DevSyncDispatch ORM model — outbound integration record.

**DevSyncDispatch** records the outbound payload sent to a DevSync system for a
technical / developer-actionable finding and its remediation plan, and tracks
the inbound status/evidence callbacks received in response.

DevSync is an integration surface only. It is **never** the source of truth for
governance: CompliAGL retains the canonical finding and remediation state, and a
DevSync ``COMPLETED`` callback never by itself resolves a finding.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import DevSyncDispatchStatus


class DevSyncDispatch(CanonicalMixin, Base):
    """An outbound DevSync dispatch and its inbound callback state."""

    __tablename__ = "devsync_dispatches"

    finding_id = Column(String, nullable=False, index=True)
    remediation_plan_id = Column(String, nullable=True, index=True)

    # The adapter used and the external system's reference for the work item.
    adapter = Column(String, nullable=False)
    external_reference = Column(String, nullable=True, index=True)
    # Opaque callback reference DevSync must echo back on every callback.
    callback_reference = Column(String, nullable=False, index=True)

    # The exact outbound payload that was sent (JSON text).
    payload = Column(Text, nullable=False, default="{}")

    status = Column(
        String, nullable=False, default=DevSyncDispatchStatus.PENDING.value
    )
    # Latest inbound developer-reported status (DevSyncCallbackStatus).
    last_callback_status = Column(String, nullable=True)
    # JSON list of received callbacks (status + note + evidence references).
    callbacks = Column(Text, nullable=False, default="[]")

    dispatched_at = Column(DateTime(timezone=True), nullable=True)
    last_callback_at = Column(DateTime(timezone=True), nullable=True)

    payload_hash = Column(String, nullable=True, index=True)
