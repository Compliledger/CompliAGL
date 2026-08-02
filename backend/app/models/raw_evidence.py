"""RawEvidence ORM model.

**RawEvidence** is a single evidence item exactly as returned by a connector,
before validation or normalization. It always carries provenance and a payload
hash. When the payload is sensitive it is held by *secure reference* rather than
inline, so sensitive data never has to move through — or be copied out of — the
runtime. Evidence is never fabricated: an item that could not be collected is
recorded with a non-``COLLECTED`` ``collection_status`` and no payload.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class RawEvidence(CanonicalMixin, Base):
    """A single evidence item as collected from a source."""

    __tablename__ = "raw_evidence"

    # Linkage to the collection run and the requirement being satisfied.
    collection_job_id = Column(String, nullable=False, index=True)
    evidence_requirement_id = Column(String, nullable=False, index=True)
    policy_resolution_id = Column(String, nullable=True, index=True)

    # Source identity + type (provenance anchors).
    source_id = Column(String, nullable=False, index=True)
    source_type = Column(String, nullable=False, index=True)

    # Runtime bindings the evidence attests to.
    subject_id = Column(String, nullable=True, index=True)
    target_id = Column(String, nullable=True, index=True)
    intent_id = Column(String, nullable=True, index=True)

    # Temporal fields.
    collected_at = Column(DateTime(timezone=True), nullable=True)
    issued_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # Payload: inline JSON *or* a secure reference (never both for sensitive
    # payloads). ``payload_hash`` binds whichever form is present.
    payload = Column(Text, nullable=True)
    payload_reference = Column(String, nullable=True)
    payload_hash = Column(String, nullable=True, index=True)
    # Non-sensitive, source-published claims used for normalization. Kept
    # separate from ``payload`` so a sensitive payload can be held by reference
    # while its shareable claims remain available downstream.
    claims = Column(Text, nullable=True)

    # Classification + provenance + status.
    sensitivity = Column(String, nullable=False, default="INTERNAL")
    issuer = Column(String, nullable=True)
    signature = Column(Text, nullable=True)
    provenance = Column(Text, nullable=False, default="{}")
    collection_status = Column(String, nullable=False, index=True)
    error = Column(Text, nullable=True)
