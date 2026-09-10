"""EscalationApproval ORM model — canonical first-class resource.

An **EscalationApproval** is the durable record of a human approving an
``ESCALATED`` decision that escalated *for human approval* (the finding type
``ESCALATION_APPROVAL_REQUIRED``). It is only ever created after the approver's
authority to approve **this** action has been verified against CompliIdentity at
approval time (see ``escalation_approval_service``), and it is time-bounded
(``valid_until``).

It is an *input* to a fact-driven re-decision — never a substitute for one: the
deterministic engine still produces a new ``Decision``, with the prior
``ESCALATED`` decision preserved and superseded. ``approver_authority_hash``
binds the approver's verified authority snapshot into this record's lineage, the
same content-hash binding pattern used for ``Decision.authority_hash``.
"""

from __future__ import annotations

from sqlalchemy import Column, DateTime, String, Text

from app.core.database import Base
from app.models._mixins import CanonicalMixin
from app.utils.canonical_enums import EscalationApprovalStatus


class EscalationApproval(CanonicalMixin, Base):
    """A time-bounded, authority-verified human approval of an escalated decision."""

    __tablename__ = "escalation_approvals"

    # Stable, human-referenceable identifier (distinct from the surrogate ``id``):
    # ``"EAP-" + approval_hash[:16]``.
    escalation_approval_id = Column(String, nullable=False, index=True)

    # --- What is being approved ---
    # The ``ESCALATED`` decision this approval authorises re-evaluation of.
    decision_id = Column(String, nullable=False, index=True)
    intent_id = Column(String, nullable=True, index=True)

    # --- Who approved, and the authority evidence ---
    approver_principal_id = Column(String, nullable=False, index=True)
    # CompliIdentity principal type from the matched ``applicable_approvals``
    # entry — must be ``HUMAN`` for the approval to be accepted (verified in
    # escalation_approval_service, persisted here for the evidence trail).
    approver_principal_type = Column(String, nullable=True)
    # Content hash of the normalised authority-context probe made for the
    # approver at approval time. CompliIdentity is the system of record for the
    # snapshot itself; this binds its identity into the approval's lineage.
    approver_authority_hash = Column(String, nullable=True)

    rationale = Column(Text, nullable=False)

    # --- Validity window ---
    granted_at = Column(DateTime(timezone=True), nullable=False)
    valid_until = Column(DateTime(timezone=True), nullable=False)

    # --- Lifecycle ---
    status = Column(
        String, nullable=False, default=EscalationApprovalStatus.ACTIVE.value
    )
    # The new ``Decision`` produced by the re-decision that consumed this approval.
    consumed_by_decision_id = Column(String, nullable=True, index=True)

    # --- Determinism / provenance ---
    approval_hash = Column(String, nullable=True, index=True)
