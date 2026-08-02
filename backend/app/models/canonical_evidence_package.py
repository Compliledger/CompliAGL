"""CanonicalEvidencePackage ORM model.

A **CanonicalEvidencePackage** is the final, deterministic bundle for one
evaluation. It references the normalized evidence collected for that evaluation,
maps evidence to the requirements and controls it satisfies, and enumerates the
missing and invalid evidence explicitly (so an absent or rejected item can never
be silently treated as satisfied). A deterministic ``package_hash`` binds the
package contents; the hash is computed only over hashes and references, so no
sensitive payload is ever included.
"""

from __future__ import annotations

from sqlalchemy import Column, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin


class CanonicalEvidencePackage(CanonicalMixin, Base):
    """The canonical evidence bundle produced for an evaluation."""

    __tablename__ = "canonical_evidence_packages"

    evaluation_id = Column(String, nullable=False, index=True)
    policy_resolution_id = Column(String, nullable=True, index=True)
    evidence_requirement_set_id = Column(String, nullable=True, index=True)
    collection_job_id = Column(String, nullable=True, index=True)

    normalized_evidence_references = Column(Text, nullable=False, default="[]")
    requirement_mappings = Column(Text, nullable=False, default="[]")
    control_mappings = Column(Text, nullable=False, default="[]")
    missing_evidence = Column(Text, nullable=False, default="[]")
    invalid_evidence = Column(Text, nullable=False, default="[]")
    reason_codes = Column(Text, nullable=False, default="[]")

    package_hash = Column(String, nullable=True, index=True)
