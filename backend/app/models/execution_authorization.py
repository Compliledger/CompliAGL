"""ExecutionAuthorization ORM model — canonical first-class resource.

An **ExecutionAuthorization** is the gate between an APPROVED decision and
external execution. It carries a one-time authorization token, optional
execution constraints, and a lifecycle status so an authorization can be
consumed, revoked, or expired.
"""

from __future__ import annotations

from sqlalchemy import BigInteger, Boolean, Column, DateTime, String, Text

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

    # --- Narrow binding to the governed action ---
    actor_id = Column(String, nullable=True, index=True)
    target_id = Column(String, nullable=True, index=True)
    authorized_action = Column(String, nullable=True)
    authorized_parameter_constraints = Column(Text, nullable=True)
    max_amount_minor = Column(BigInteger, nullable=True)
    max_amount_currency = Column(String, nullable=True)
    permitted_execution_system = Column(String, nullable=True)

    # --- Replay protection + idempotency + one-time-use lifecycle ---
    issued_at = Column(DateTime(timezone=True), nullable=True)
    nonce = Column(String, nullable=True, index=True)
    idempotency_key = Column(String, nullable=True, index=True)
    one_time_use = Column(Boolean, nullable=False, default=True)
    consumed_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)
    revocation_reason = Column(String, nullable=True)

    # --- Bound hashes (independently verifiable) ---
    policy_package_hash = Column(String, nullable=True)
    assessment_hash = Column(String, nullable=True)
    evidence_package_hash = Column(String, nullable=True)
    decision_hash = Column(String, nullable=True)

    # --- Signature ---
    signer_key_id = Column(String, nullable=True)
    signature = Column(Text, nullable=True)
    authorization_hash = Column(String, nullable=True, index=True)
