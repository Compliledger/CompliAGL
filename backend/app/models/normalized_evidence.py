"""NormalizedEvidence ORM model.

**NormalizedEvidence** is the canonical, platform-neutral projection of a single
*validated* evidence item. Source-specific payloads are transformed into a fixed
canonical schema: subject, target, source, issuer, normalized claims, monetary
values expressed in **integer minor units** (never floats), a validity window,
the validation status, and both the source and normalized payload hashes plus a
provenance reference. Sensitive source payloads are **never** copied here — only
their hashes are retained — so normalized evidence is safe to project into public
proofs.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class NormalizedEvidence(CanonicalMixin, Base):
    """Canonical projection of a validated evidence item."""

    __tablename__ = "normalized_evidence"

    raw_evidence_id = Column(String, nullable=False, index=True)
    validation_result_id = Column(String, nullable=False, index=True)
    evidence_requirement_id = Column(String, nullable=False, index=True)
    collection_job_id = Column(String, nullable=True, index=True)
    policy_resolution_id = Column(String, nullable=True, index=True)

    evidence_type = Column(String, nullable=True, index=True)
    subject = Column(String, nullable=True, index=True)
    target = Column(String, nullable=True, index=True)
    source = Column(String, nullable=True, index=True)
    issuer = Column(String, nullable=True)

    # Canonical claims (JSON). Monetary values inside are integer minor units.
    normalized_claims = Column(Text, nullable=False, default="{}")

    valid_from = Column(DateTime(timezone=True), nullable=True)
    valid_until = Column(DateTime(timezone=True), nullable=True)

    validation_status = Column(String, nullable=False, index=True)
    source_payload_hash = Column(String, nullable=True, index=True)
    normalized_payload_hash = Column(String, nullable=True, index=True)
    provenance_reference = Column(String, nullable=True)
