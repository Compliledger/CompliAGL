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

The approver check is two-layered: (1)
``authority_context_service.verify_approver_authority`` — ``sufficient == true``
on a live ``approve`` probe plus the approver's own ``principal_type == HUMAN``;
(2) here — the approver's principal type must match
``Decision.required_approver_types``, CompliIdentity's own decision-time
declaration of which approver type the escalated action requires (empty, so
layer 1 stands alone, when CompliIdentity named no approval requirement — e.g.
a package amount-threshold escalation).
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.decision import Decision
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


def _str_list(raw: Optional[str]) -> list[str]:
    try:
        parsed = json.loads(raw or "[]")
    except (ValueError, TypeError):
        return []
    return [str(c) for c in parsed] if isinstance(parsed, list) else []


def _reason_codes(decision) -> list[str]:
    return _str_list(decision.reason_codes)


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

    # Cross-check against CompliIdentity's own declaration (captured on the
    # Decision at decision time) of which approver type the escalated action
    # requires -- not just "any human". Empty when CompliIdentity named no
    # approval requirement for the action (e.g. a package amount-threshold
    # escalation), in which case the verify_approver_authority checks stand.
    required_types = _str_list(decision.required_approver_types)
    if required_types and verification.approver_principal_type not in required_types:
        raise AuthorityVerificationError(
            "approver_type_mismatch",
            "CompliIdentity requires an approver of type "
            f"{required_types} for this escalation; the submitted approver is "
            f"{verification.approver_principal_type!r}.",
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


def apply(
    db: Session,
    organization_id: str,
    *,
    escalation_approval_id: str,
) -> Decision:
    """Step 2: consume an ACTIVE approval by re-deciding its escalated decision.

    Thin orchestration -- looks up the approval, requires it ``ACTIVE``, and
    runs ``decision_service.decide_for_resolution(prior_decision_id=<the
    escalated decision>)``. The engine reads the approval as the ``approval``
    runtime fact; whether that upgrades the escalation is package-authored, and
    marking the approval ``CONSUMED`` (only on an APPROVED outcome) happens
    inside ``decide_for_resolution``.
    """
    org = organization_id
    approval = EscalationApprovalRepository(db).get(org, escalation_approval_id)
    if approval is None:
        raise NotFoundError(
            f"EscalationApproval not found: {escalation_approval_id}"
        )
    if approval.status != EscalationApprovalStatus.ACTIVE.value:
        raise ConflictError(
            f"EscalationApproval {approval.escalation_approval_id} is "
            f"{approval.status}, not ACTIVE -- it cannot be applied."
        )
    decision = DecisionRepository(db).get(org, approval.decision_id)
    if decision is None:
        raise NotFoundError(f"Decision not found: {approval.decision_id}")
    resolution_id = decision.policy_resolution_id or decision.evaluation_id
    return decision_service.decide_for_resolution(
        db, org, resolution_id, prior_decision_id=approval.decision_id
    )


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
