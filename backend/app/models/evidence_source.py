"""EvidenceSource ORM model — the evidence source registry.

An **EvidenceSource** is a persistent registry entry describing a connector that
CompliAGL can use to collect evidence. It records the connector's generic source
type, the evidence types it can serve, an *indirect* reference to its
authentication configuration (never inline secrets), whether it is a mock
connector, and its trusted issuers. The registry is platform-neutral — it never
encodes a concrete domain such as an airline or a payment application.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class EvidenceSource(CanonicalMixin, Base):
    """Persistent registry entry for an evidence connector."""

    __tablename__ = "evidence_sources"

    connector_id = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False, index=True)
    supported_evidence_types = Column(Text, nullable=False, default="[]")
    auth_config_reference = Column(String, nullable=True)
    is_mock = Column(Boolean, nullable=False, default=False)
    trusted_issuers = Column(Text, nullable=False, default="[]")
    timeout_seconds = Column(String, nullable=True)
    retry_policy = Column(Text, nullable=True)
    status = Column(String, nullable=False, default="ACTIVE")
