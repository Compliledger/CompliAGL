"""PolicyResolution ORM model — canonical first-class resource.

A **PolicyResolution** is the persistent output of the *Policy Resolution*
runtime stage. That stage runs **before** and **separately from** the decision
engine: it identifies the candidate executable governance packages for a
concrete (actor, intent, target, context) tuple, filters them (status,
effective/expiration dates, organization, jurisdiction, environment, actor
type, intent type, target type, asset/transaction characteristics), applies
policy hierarchy and priority, detects conflicts, applies explicit
conflict-resolution rules, and records the *exact* package and requirement
versions selected.

Structured fields (candidate ids, selected packages, conflicts, observed
selection facts, reason codes) are stored as JSON text. Deterministic
``input_hash`` and ``result_hash`` bind the inputs and output so identical
inputs and package versions produce identical hashes.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import PolicyResolutionStatus


class PolicyResolution(CanonicalMixin, Base):
    """Persistent record of a deterministic policy-resolution run."""

    __tablename__ = "policy_resolutions"

    # --- Runtime inputs (the tuple being governed) ---
    actor_identity_id = Column(String, nullable=False, index=True)
    intent_id = Column(String, nullable=False, index=True)
    target_id = Column(String, nullable=True, index=True)
    operational_context_id = Column(String, nullable=True, index=True)

    status = Column(
        String, nullable=False, default=PolicyResolutionStatus.RESOLVED.value
    )

    # --- Selection output ---
    # All published packages considered for the organization.
    candidate_package_ids = Column(Text, nullable=False, default="[]")
    # The governing packages actually selected, each recording the exact
    # package id + version + hash and the requirement ids + versions selected.
    selected_packages = Column(Text, nullable=False, default="[]")
    # Detected conflicts and the explicit conflict-resolution applied.
    conflicts = Column(Text, nullable=False, default="[]")
    # The runtime facts used for scope filtering (jurisdiction, environment,
    # actor/intent/target type, asset/transaction characteristics).
    selection_facts = Column(Text, nullable=True)
    reason_codes = Column(Text, nullable=False, default="[]")

    # --- Determinism / provenance ---
    engine_version = Column(String, nullable=False)
    input_hash = Column(String, nullable=True, index=True)
    result_hash = Column(String, nullable=True, index=True)
    resolved_at = Column(DateTime(timezone=True), nullable=True)
