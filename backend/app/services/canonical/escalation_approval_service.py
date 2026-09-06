"""Escalation-approval service — step 1 of human-approval orchestration.

``submit()`` records an **authority-verified** human approval of an
``ESCALATED`` decision that escalated for human approval (finding type
``ESCALATION_APPROVAL_REQUIRED``), then returns. It deliberately does **not**
re-decide: a separate, explicit re-decision call
(``decision_service.decide_for_resolution(..., prior_decision_id=)``) consumes
the approval as a runtime fact. Two steps, each producing its own reviewable
evidence.

Every rejection is fail-closed and typed (``AuthorityVerificationError`` /
``ConflictError`` / ``NotFoundError``) — an approval is only ever persisted when
the approver's authority to approve *this* action is confirmed against
CompliIdentity at submit time.

**Known limitation (to be closed in the re-decision commit):** the check here
is ``sufficient == true`` on the approver's ``approve`` probe plus "the
approver is a HUMAN principal". It does **not** yet cross-check that the
approver is the *required* approver type CompliIdentity declared for the
escalated action — that declaration
(``applicable_approvals[].approver_principal_type``) lives on the escalating
actor's decision-time probe and must be persisted on the Decision first. See
``authority_context_service.verify_approver_authority``.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.escalation_approval import EscalationApproval
from app.repositories.canonical import (
    DecisionRepository,
    EscalationApprovalRepository,
    PolicyResolutionRepository,
)
from app.services.canonical import authority_context_service, decision_service
from app.services.canonical.errors import (
    AuthorityVerificationError,
    ConflictError,
    NotFoundError,
)
from app.services.canonical.runtime_facts import build_authority_facts
from app.utils.canonical_enums import (
    DecisionOutcome,
    DecisionSupersessionStatus,
    EscalationApprovalStatus,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now


def _ttl_seconds() -> int:
    return int(getattr(settings, "ESCALATION_APPROVAL_TTL_SECONDS", 900) or 900)


def _reason_codes(decision) -> list[str]:
    try:
        codes = json.loads(decision.reason_codes or "[]")
    except (ValueError, TypeError):
        return []
    return [str(c) for c in codes] if isinstance(codes, list) else []


def _approval_hash(approval: EscalationApproval) -> str:
    return hash_dict(
        {
            "organization_id": approval.organization_id,
            "decision_id": approval.decision_id,
            "approver_principal_id": approval.approver_principal_id,
            "approver_authority_hash": approval.approver_authority_hash,
            "rationale": approval.rationale,
            "granted_at": approval.granted_at.isoformat(),
            "valid_until": approval.valid_until.isoformat(),
        }
    )


def submit(
    db: Session,
    organization_id: str,
    *,
    decision_id: str,
    approver_principal_id: str,
    rationale: str,
    valid_until: Optional[datetime] = None,
) -> EscalationApproval:
    """Record an authority-verified human approval of an escalated decision.

    Does not re-decide. The returned :class:`EscalationApproval` is ``ACTIVE``
    and unconsumed; a subsequent explicit re-decision reads it as a runtime
    fact and marks it ``CONSUMED``.
    """
    org = organization_id

    decision = DecisionRepository(db).get(org, decision_id)
    if decision is None:
        raise NotFoundError(f"Decision not found: {decision_id}")

    # The decision must currently be an unresolved *policy-condition*
    # escalation. ESCALATED_BY_POLICY is emitted only by
    # decision_service._resolve_outcome and cannot be forged by a package.
    if (
        decision.outcome != DecisionOutcome.ESCALATED.value
        or decision.supersession_status
        != DecisionSupersessionStatus.CURRENT.value
        or "ESCALATED_BY_POLICY" not in _reason_codes(decision)
    ):
        raise ConflictError(
            "An escalation approval can only be submitted for a current, "
            f"policy-escalated decision (decision {decision_id} is "
            f"{decision.outcome} / {decision.supersession_status})."
        )

    resolution_id = decision.policy_resolution_id or decision.evaluation_id
    resolution = (
        PolicyResolutionRepository(db).get(org, resolution_id)
        if resolution_id
        else None
    )
    if resolution is None:
        raise NotFoundError(
            f"PolicyResolution not found for decision {decision_id}"
        )
    actor, intent, _target, _context = decision_service._gather_inputs(
        db, org, resolution
    )

    # Anti-self-approval: the approver must be a different principal from the
    # actor whose action escalated.
    actor_principal_id = decision_service._authority_principal_id(actor)
    if actor_principal_id and approver_principal_id == actor_principal_id:
        raise AuthorityVerificationError(
            "self_approval",
            "The approver must be a different principal from the actor whose "
            "action escalated.",
        )

    # Verify the approver's authority to APPROVE this action, right now, against
    # CompliIdentity. Same resource / resource_instance / amount as the intent;
    # action forced to "approve".
    probe = decision_service._authority_request_params(intent)
    verification = authority_context_service.verify_approver_authority(
        authority_context_service.default_client(),
        organization_id=org,
        approver_principal_id=approver_principal_id,
        resource=probe["resource"],
        action="approve",
        resource_instance=probe.get("resource_instance"),
        attribute=probe.get("attribute"),
        value=probe.get("value"),
    )
    if not verification.authorized:
        raise AuthorityVerificationError(
            verification.reason,
            "Approver authority could not be verified against CompliIdentity "
            f"({verification.reason}); no approval recorded.",
        )

    now = utc_now()
    approval = EscalationApproval(
        organization_id=org,
        decision_id=decision.id,
        intent_id=intent.id,
        approver_principal_id=approver_principal_id,
        approver_principal_type=verification.approver_principal_type,
        approver_authority_hash=hash_dict(
            build_authority_facts(verification.context)
        ),
        rationale=rationale,
        granted_at=now,
        valid_until=valid_until or (now + timedelta(seconds=_ttl_seconds())),
        status=EscalationApprovalStatus.ACTIVE.value,
    )
    approval.approval_hash = _approval_hash(approval)
    approval.escalation_approval_id = "EAP-" + approval.approval_hash[:16]
    return EscalationApprovalRepository(db).add(approval)


def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[EscalationApproval]:
    return EscalationApprovalRepository(db).get(organization_id, resource_id)


def list_for_decision(
    db: Session, organization_id: str, decision_id: str
):
    return EscalationApprovalRepository(db).list_for_decision(
        organization_id, decision_id
    )
