"""ExecutionAuthorization ORM model — canonical first-class resource.

An **ExecutionAuthorization** is the gate between an APPROVED decision and
external execution. It carries a one-time authorization token, optional
execution constraints, and a lifecycle status so an authorization can be
consumed, revoked, or expired.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import AuthorizationStatus


class ExecutionAuthorization(CanonicalMixin, Base):
    """Persistent authorization permitting external execution."""

    __tablename__ = "execution_authorizations"

    decision_id = Column(String, nullable=False, index=True)
    intent_id = Column(String, nullable=False, index=True)

    status = Column(
        String, nullable=False, default=AuthorizationStatus.PENDING.value
    )
    authorization_token = Column(String, nullable=True, index=True)
    constraints = Column(Text, nullable=True)

    authorized_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
