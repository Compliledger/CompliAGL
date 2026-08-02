"""GovernanceEvaluation ORM model — canonical first-class resource.

A **GovernanceEvaluation** is the record that ties an actor identity, an intent,
a target, and an operational context together for a single governance run. It
is the join-point of the canonical runtime sequence and the anchor the rest of
the decision/authorization/execution/proof chain references.
"""

from __future__ import annotations

from sqlalchemy import Column, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import EvaluationStatus


class GovernanceEvaluation(CanonicalMixin, Base):
    """Persistent record binding actor, intent, target, and context."""

    __tablename__ = "governance_evaluations"

    actor_identity_id = Column(String, nullable=False, index=True)
    intent_id = Column(String, nullable=False, index=True)
    target_id = Column(String, nullable=True, index=True)
    operational_context_id = Column(String, nullable=True, index=True)

    status = Column(
        String, nullable=False, default=EvaluationStatus.PENDING.value
    )
    # Resolved decision outcome, once evaluated (nullable while PENDING).
    outcome = Column(String, nullable=True)
    reason_codes = Column(Text, nullable=False, default="[]")

    evaluation_hash = Column(String, nullable=True, index=True)
