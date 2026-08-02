"""ReevaluationRun ORM model — canonical first-class re-evaluation record.

A **ReevaluationRun** is the durable record of one automated re-evaluation of a
governed outcome, triggered by a :class:`app.models.monitoring_event.MonitoringEvent`.

Re-evaluation never overwrites history: the run records which triggering event
caused it, the impact-analysis result (which objects were affected), and the
*new* immutable records it produced (a new assessment, a new decision that
supersedes the prior current decision, any invalidated authorizations, and a new
AIProof that supersedes the prior proof). Prior records remain available and are
only linked from the run, never mutated away.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import ReevaluationStatus


class ReevaluationRun(CanonicalMixin, Base):
    """Persistent automated re-evaluation run."""

    __tablename__ = "reevaluation_runs"

    # The triggering monitoring event (link back to the cause).
    monitoring_event_id = Column(String, nullable=False, index=True)
    change_type = Column(String, nullable=True, index=True)
    correlation_id = Column(String, nullable=True, index=True)

    status = Column(
        String, nullable=False, default=ReevaluationStatus.PENDING.value, index=True
    )

    # Scope resolved by impact analysis.
    intent_id = Column(String, nullable=True, index=True)
    evaluation_id = Column(String, nullable=True, index=True)

    # The full impact-analysis result (JSON text): affected intents, evaluations,
    # decisions, authorizations, findings, aiproofs and canonical proof packages.
    impact = Column(Text, nullable=False, default="{}")

    # New immutable records produced by the run.
    prior_decision_id = Column(String, nullable=True, index=True)
    new_decision_id = Column(String, nullable=True, index=True)
    new_assessment_id = Column(String, nullable=True, index=True)
    prior_aiproof_id = Column(String, nullable=True, index=True)
    new_aiproof_id = Column(String, nullable=True, index=True)

    # Authorizations invalidated because current conditions no longer support
    # them (JSON list of ids).
    invalidated_authorization_ids = Column(Text, nullable=False, default="[]")

    resulting_outcome = Column(String, nullable=True)
    reason_codes = Column(Text, nullable=False, default="[]")

    error = Column(Text, nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
