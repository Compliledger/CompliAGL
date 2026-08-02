"""DevSync integration service.

Builds the outbound payload for a technical / developer-actionable finding and
its remediation plan, dispatches it through a formal :class:`DevSyncAdapter`, and
processes inbound status and evidence callbacks.

CompliAGL retains the canonical finding and remediation state. An inbound
``COMPLETED`` callback records developer progress and may submit resolution
evidence, but it never resolves the finding on its own — resolution still flows
through resolution validation and a new deterministic decision.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.devsync_dispatch import DevSyncDispatch
from app.repositories.canonical import (
    DevSyncDispatchRepository,
    FindingRepository,
    RemediationPlanRepository,
)
from app.schemas.canonical.remediation import (
    DevSyncCallbackRequest,
    DevSyncDispatchRequest,
    ResolutionEvidenceSubmit,
)
from app.services.canonical import resolution_evidence_service
from app.services.canonical.devsync_adapter import (
    DevSyncOutboundPayload,
    get_adapter,
)
from app.services.canonical.errors import ConflictError, NotFoundError
from app.utils.canonical_enums import (
    DevSyncCallbackStatus,
    DevSyncDispatchStatus,
    FindingStatus,
    RemediationPlanStatus,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import ensure_aware, utc_now


def _load(raw: Optional[str], default: Any = None) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


def build_outbound_payload(
    db: Session,
    organization_id: str,
    finding,
    plan,
    callback_reference: str,
) -> DevSyncOutboundPayload:
    """Assemble the canonical outbound DevSync payload."""
    control_ids = _load(finding.control_ids, []) or []
    requirement_ids = _load(finding.requirement_ids, []) or []
    instructions: list[dict[str, Any]] = []
    required_evidence: list[dict[str, Any]] = []
    if plan is not None:
        instructions = _load(plan.remediation_actions, []) or []
        required_evidence = _load(plan.required_resolution_evidence, []) or []

    due = plan.due_date if plan is not None else finding.due_date
    return DevSyncOutboundPayload(
        finding_id=finding.finding_id,
        source_decision_id=finding.decision_id,
        callback_reference=callback_reference,
        affected_actor_id=finding.actor_id,
        affected_target_id=finding.target_id,
        affected_system=finding.intent_id,
        control_ids=[str(c) for c in control_ids],
        requirement_ids=[str(r) for r in requirement_ids],
        severity=finding.severity,
        remediation_plan_id=(plan.remediation_plan_id if plan is not None else None),
        remediation_instructions=instructions,
        required_resolution_evidence=required_evidence,
        due_date=(ensure_aware(due).isoformat() if due is not None else None),
    )


def dispatch(db: Session, payload: DevSyncDispatchRequest) -> DevSyncDispatch:
    """Dispatch a finding + plan to DevSync through the adapter."""
    org = payload.organization_id
    finding = FindingRepository(db).get(org, payload.finding_id)
    if finding is None:
        raise NotFoundError(f"Finding not found: {payload.finding_id}")
    if finding.terminal:
        raise ConflictError(
            "A terminal finding cannot be dispatched to DevSync "
            f"({finding.finding_id})."
        )

    plan = None
    if payload.remediation_plan_id:
        plan = RemediationPlanRepository(db).get(org, payload.remediation_plan_id)
        if plan is None:
            raise NotFoundError(
                f"RemediationPlan not found: {payload.remediation_plan_id}"
            )
    else:
        plan = RemediationPlanRepository(db).latest_for_finding(org, finding.id)

    adapter = get_adapter(payload.adapter)
    # Deterministic callback reference bound to the finding + plan.
    callback_reference = "cb-" + hash_dict(
        {
            "organization_id": org,
            "finding_id": finding.id,
            "remediation_plan_id": plan.id if plan is not None else None,
        }
    )[:20]

    outbound = build_outbound_payload(db, org, finding, plan, callback_reference)
    payload_dict = outbound.to_dict()

    now = utc_now()
    dispatch_obj = DevSyncDispatch(
        organization_id=org,
        finding_id=finding.id,
        remediation_plan_id=plan.id if plan is not None else None,
        adapter=adapter.name,
        callback_reference=callback_reference,
        payload=json.dumps(payload_dict),
        status=DevSyncDispatchStatus.PENDING.value,
        callbacks="[]",
        payload_hash=hash_dict(payload_dict),
    )

    result = adapter.dispatch(outbound)
    if result.accepted:
        dispatch_obj.status = DevSyncDispatchStatus.DISPATCHED.value
        dispatch_obj.external_reference = result.external_reference
        dispatch_obj.dispatched_at = now
    else:
        dispatch_obj.status = DevSyncDispatchStatus.FAILED.value

    saved = DevSyncDispatchRepository(db).add(dispatch_obj)

    # Reflect dispatch on the plan (governance-owned state).
    if plan is not None and result.accepted:
        if plan.status not in {
            RemediationPlanStatus.VALIDATED.value,
            RemediationPlanStatus.CANCELLED.value,
        }:
            plan.status = RemediationPlanStatus.DISPATCHED.value
            RemediationPlanRepository(db).save(plan)
    if result.accepted and finding.status in {
        FindingStatus.OPEN.value,
        FindingStatus.ASSIGNED.value,
    }:
        finding.status = FindingStatus.IN_PROGRESS.value
        FindingRepository(db).save(finding)

    return saved


def handle_callback(
    db: Session, payload: DevSyncCallbackRequest
) -> DevSyncDispatch:
    """Process an inbound DevSync status/evidence callback.

    Any submitted evidence is ingested as :class:`ResolutionEvidence` and
    validated through the same evidence architecture. The callback never
    resolves the finding by itself.
    """
    org = payload.organization_id
    repo = DevSyncDispatchRepository(db)
    dispatch_obj = repo.get_by_callback_reference(org, payload.callback_reference)
    if dispatch_obj is None:
        raise NotFoundError(
            f"DevSync dispatch not found for callback reference: "
            f"{payload.callback_reference}"
        )

    finding = FindingRepository(db).get(org, dispatch_obj.finding_id)

    now = utc_now()
    submitted_evidence_ids: list[str] = []
    for item in payload.evidence:
        submit = ResolutionEvidenceSubmit(
            organization_id=org,
            finding_id=dispatch_obj.finding_id,
            remediation_plan_id=dispatch_obj.remediation_plan_id,
            evidence_type=item.evidence_type,
            issuer=item.issuer,
            subject_id=item.subject_id,
            target_id=item.target_id,
            intent_id=item.intent_id,
            issued_at=item.issued_at,
            expires_at=item.expires_at,
            signature=item.signature,
            claims=item.claims,
            payload=item.payload,
            provenance=item.provenance,
            submitted_via="DEVSYNC",
        )
        evidence = resolution_evidence_service.submit(db, submit)
        submitted_evidence_ids.append(evidence.id)

    callbacks = _load(dispatch_obj.callbacks, []) or []
    callbacks.append(
        {
            "status": payload.status.value,
            "note": payload.note,
            "external_reference": payload.external_reference,
            "evidence_ids": submitted_evidence_ids,
            "received_at": now.isoformat(),
        }
    )
    dispatch_obj.callbacks = json.dumps(callbacks)
    dispatch_obj.last_callback_status = payload.status.value
    dispatch_obj.last_callback_at = now
    if payload.external_reference:
        dispatch_obj.external_reference = payload.external_reference
    if payload.status in {
        DevSyncCallbackStatus.RECEIVED,
        DevSyncCallbackStatus.IN_PROGRESS,
        DevSyncCallbackStatus.BLOCKED,
        DevSyncCallbackStatus.COMPLETED,
    }:
        dispatch_obj.status = DevSyncDispatchStatus.ACKNOWLEDGED.value

    saved = repo.save(dispatch_obj)

    # Mirror developer-reported progress onto governance-owned state, but never
    # close the finding from a callback.
    if finding is not None and finding.status != FindingStatus.CLOSED.value:
        if payload.status == DevSyncCallbackStatus.BLOCKED:
            finding.status = FindingStatus.BLOCKED.value
            FindingRepository(db).save(finding)
        elif payload.status in {
            DevSyncCallbackStatus.RECEIVED,
            DevSyncCallbackStatus.IN_PROGRESS,
        } and finding.status in {
            FindingStatus.OPEN.value,
            FindingStatus.ASSIGNED.value,
            FindingStatus.BLOCKED.value,
        }:
            finding.status = FindingStatus.IN_PROGRESS.value
            FindingRepository(db).save(finding)

    if dispatch_obj.remediation_plan_id and payload.status == (
        DevSyncCallbackStatus.COMPLETED
    ):
        plan = RemediationPlanRepository(db).get(
            org, dispatch_obj.remediation_plan_id
        )
        if plan is not None and plan.status not in {
            RemediationPlanStatus.VALIDATED.value,
            RemediationPlanStatus.CANCELLED.value,
        }:
            plan.status = RemediationPlanStatus.REMEDIATION_COMPLETE.value
            RemediationPlanRepository(db).save(plan)

    return saved


# --------------------------------------------------------------------------- #
# Reads
# --------------------------------------------------------------------------- #
def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[DevSyncDispatch]:
    return DevSyncDispatchRepository(db).get(organization_id, resource_id)


def list_for_finding(
    db: Session, organization_id: str, finding_id: str
) -> Sequence[DevSyncDispatch]:
    return DevSyncDispatchRepository(db).list_for_finding(organization_id, finding_id)
