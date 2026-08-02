"""ActorIdentity ORM model — canonical first-class resource.

An **ActorIdentity** is the resolved, persistent identity of whoever submits an
intent. It is deliberately *pluggable*: a DID or VC is not required for every
actor. The model can carry a Hedera account / Hedera Agent Account, an
OAuth/OIDC identity, an enterprise service identity, or nothing but internal
identifiers.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import (
    CredentialType,
    RevocationStatus,
    VerificationStatus,
)


class ActorIdentity(CanonicalMixin, Base):
    """Persistent, pluggable identity of an acting entity."""

    __tablename__ = "actor_identities"

    # --- Core identity ---
    actor_type = Column(String, nullable=False)
    human_principal_id = Column(String, nullable=True)
    external_account_id = Column(String, nullable=True, index=True)
    wallet_or_agent_account_id = Column(String, nullable=True, index=True)

    # --- Pluggable credential (DID / VC / Hedera / OAuth / enterprise) ---
    credential_type = Column(
        String, nullable=False, default=CredentialType.NONE.value
    )
    credential_issuer = Column(String, nullable=True)
    credential_reference = Column(String, nullable=True)

    # --- Verification & validity ---
    verification_status = Column(
        String, nullable=False, default=VerificationStatus.UNVERIFIED.value
    )
    valid_from = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    revocation_status = Column(
        String, nullable=False, default=RevocationStatus.ACTIVE.value
    )

    # --- Free-form metadata (JSON text) ---
    identity_metadata = Column(Text, nullable=True)
