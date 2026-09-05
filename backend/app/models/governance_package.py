"""ExecutableGovernancePackage ORM model — the CompliLedger → CompliAGL contract.

An **ExecutableGovernancePackage** is the formal, machine-readable, executable
unit that CompliLedger publishes to CompliAGL. CompliLedger ingests
human-readable policies, regulations, standards, contracts, and requirements and
converts them into executable governance. CompliAGL does **not** reinterpret
human-language policy at runtime — it consumes approved, versioned packages and
applies them deterministically to a specific actor, intent, target, and
operational context.

The structured contents (requirements, applicability rules, control
definitions, evidence requirements, decision conditions, conflict-resolution
rules, and metadata) are stored as JSON text and validated against a JSON
Schema. A deterministic ``package_hash`` binds the published contents so they
are immutable — any change requires a new version.
"""

from __future__ import annotations

from sqlalchemy import Boolean, Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import PackageStatus


class ExecutableGovernancePackage(CanonicalMixin, Base):
    """Persistent, versioned, executable governance package."""

    __tablename__ = "executable_governance_packages"

    # --- Identity / naming ---
    package_name = Column(String, nullable=False, index=True)
    package_version = Column(String, nullable=False)
    # ``schema_version`` (int) is provided by CanonicalMixin. ``content_schema_version``
    # captures the version of the *package content* schema published by CompliLedger.
    content_schema_version = Column(String, nullable=False, default="1.0.0")

    # --- Lifecycle ---
    status = Column(String, nullable=False, default=PackageStatus.DRAFT.value)
    effective_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)

    # --- Approval / publication provenance ---
    approved_by = Column(String, nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    published_at = Column(DateTime(timezone=True), nullable=True)
    supersedes_package_id = Column(String, nullable=True, index=True)
    superseded_by_package_id = Column(String, nullable=True, index=True)

    # --- Integrity / signing ---
    package_hash = Column(String, nullable=True, index=True)
    signature = Column(Text, nullable=True)
    signer_key_id = Column(String, nullable=True)

    # --- Source traceability (JSON text) ---
    source_document_references = Column(Text, nullable=True)
    source_requirement_references = Column(Text, nullable=True)

    # --- Executable governance content (JSON text) ---
    requirements = Column(Text, nullable=False, default="[]")
    applicability_rules = Column(Text, nullable=False, default="[]")
    control_definitions = Column(Text, nullable=False, default="[]")
    evidence_requirements = Column(Text, nullable=False, default="[]")
    decision_conditions = Column(Text, nullable=False, default="[]")
    conflict_resolution_rules = Column(Text, nullable=False, default="[]")
    package_metadata = Column(Text, nullable=True)

    # Opt-in: only packages that set this call CompliIdentity's authority-
    # context endpoint at decision time (see decision_service.py /
    # authority_context_service.py). Defaults False so every package that
    # predates this integration keeps behaving exactly as before.
    requires_authority_context = Column(Boolean, nullable=False, default=False)
