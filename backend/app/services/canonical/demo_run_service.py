"""Derived Demo #3 run-state view.

Stitches together the canonical records one governed-action attempt leaves
behind -- Intent -> Decision(s) -> EscalationApproval(s) ->
ExecutionAuthorization(s) -> ExternalExecutionResult -> CanonicalAIProof --
into one read-only view, keyed by the ``correlation_id`` every caller into
this backend already carries on every call it makes (the Astra tool layer
mints one per session in ``AstraInvocationContext``; the Execution Gateway
threads one through its whole ``evaluate_governance`` /
``approve_and_reissue`` orchestration). See ``app/astra/context.py`` and
``CompliAGL-Gateway-VERIFIED/app/clients/compliagl.py`` for those two real
callers.

This is deliberately **not** a new persisted resource: every field below is
derived, on read, from records that already exist for other reasons (the
same canonical-record philosophy used everywhere else in this codebase).
There is no new table and no new write path here.

``action_id`` in the returned view is this backend's own ``Intent.id`` --
the id of the one proposed action a governed-action attempt creates. It is
*not* the Execution Gateway's separate ``execution_id`` / SENTRY's
in-memory adapter-decision-record id, both of which are that other
service's own bookkeeping and unknown to CompliAGL.

CompliAGL's own visibility ends where the flow leaves this system:
CompliLedger fetching a Decision/AIProof to verify, and CompliAegis's
validation, are downstream continuations this repo cannot observe or drive.
``downstream`` on the returned view says so explicitly rather than guessing
at state this backend has no way to know.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.decision import Decision
from app.models.escalation_approval import EscalationApproval
from app.models.execution_authorization import ExecutionAuthorization
from app.models.external_execution_result import ExternalExecutionResult
from app.models.intent import Intent
from app.repositories.canonical import (
    CanonicalAIProofRepository,
    DecisionRepository,
    EscalationApprovalRepository,
    ExecutionAuthorizationRepository,
    ExternalExecutionResultRepository,
    IntentRepository,
)
from app.utils.canonical_enums import (
    AuthorizationStatus,
    DecisionOutcome,
    EscalationApprovalStatus,
    ExecutionResultStatus,
)

# Case id lives under this key in Intent.parameters -- the same convention
# governed_action_service.propose / astra.tools.handlers._intents_for_case
# already use. Not a first-class Intent column.
_CASE_PARAM_KEY = "compliidentity_resource_instance"

# CompliAGL's own observable stages for one governed-action run. Everything
# after PROOF_GENERATED (CompliLedger validation/reassessment, CompliAegis
# validation, an eventual COMPLETE) happens outside this backend -- see
# ``downstream`` on the returned view.
STAGE_STARTED = "STARTED"
STAGE_DENIED = "DENIED"
STAGE_AWAITING_APPROVAL = "AWAITING_APPROVAL"
STAGE_APPROVAL_SUBMITTED = "APPROVAL_SUBMITTED"
STAGE_APPROVED = "APPROVED"
STAGE_EXECUTION_AUTHORIZED = "EXECUTION_AUTHORIZED"
STAGE_ACTION_INTEGRITY_VERIFIED = "ACTION_INTEGRITY_VERIFIED"
STAGE_EXECUTION_AUTHORIZATION_REVOKED = "EXECUTION_AUTHORIZATION_REVOKED"
STAGE_EXECUTION_AUTHORIZATION_EXPIRED = "EXECUTION_AUTHORIZATION_EXPIRED"
STAGE_EXECUTED = "EXECUTED"
STAGE_EXECUTION_FAILED = "EXECUTION_FAILED"
STAGE_PROOF_GENERATED = "PROOF_GENERATED"

_DOWNSTREAM_NOTE = {
    "compliledger": (
        "not tracked by CompliAGL -- CompliLedger independently pulls "
        "Decision / AIProof records via this backend's own read API "
        "(GET /decisions/{id}, GET /aiproofs/{id}) to evaluate and produce "
        "its own proof; it does not report a status back into CompliAGL."
    ),
    "compliaegis": (
        "not tracked by CompliAGL -- CompliAegis validates by calling "
        "into this backend's own inbound API (escalation-approvals, "
        "execution-authorizations, decisions) to probe attack paths; it is "
        "a caller of CompliAGL, not a system CompliAGL calls or observes."
    ),
}


def _load(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _iso(value) -> Optional[str]:
    return value.isoformat() if value is not None else None


def _intent_params(intent: Intent) -> dict[str, Any]:
    params = _load(getattr(intent, "parameters", None), {})
    return params if isinstance(params, dict) else {}


def _case_id(intent: Intent) -> Optional[str]:
    return _intent_params(intent).get(_CASE_PARAM_KEY)


def _reason_codes(decision: Decision) -> list[str]:
    return _load(decision.reason_codes, []) or []


def _latest(rows: Sequence[Any]) -> Optional[Any]:
    if not rows:
        return None
    return max(rows, key=lambda r: r.created_at)


def _decision_view(decision: Optional[Decision]) -> Optional[dict[str, Any]]:
    if decision is None:
        return None
    return {
        "decision_id": decision.id,
        "outcome": decision.outcome,
        "reason_codes": _reason_codes(decision),
        "authority_status": decision.authority_status,
        "authority_reason": decision.authority_reason,
        "prior_decision_id": decision.prior_decision_id,
        "superseded_by_decision_id": decision.superseded_by_decision_id,
        "decided_at": _iso(decision.decided_at),
    }


def _escalation_approval_view(
    approval: Optional[EscalationApproval],
) -> Optional[dict[str, Any]]:
    if approval is None:
        return None
    return {
        "escalation_approval_id": approval.escalation_approval_id,
        "decision_id": approval.decision_id,
        "approver_principal_id": approval.approver_principal_id,
        "status": approval.status,
        "granted_at": _iso(approval.granted_at),
        "valid_until": _iso(approval.valid_until),
        "consumed_by_decision_id": approval.consumed_by_decision_id,
    }


def _authorization_view(
    auth: Optional[ExecutionAuthorization],
) -> Optional[dict[str, Any]]:
    if auth is None:
        return None
    return {
        "execution_authorization_id": auth.id,
        "status": auth.status,
        "permitted_execution_system": auth.permitted_execution_system,
        "one_time_use": auth.one_time_use,
        "issued_at": _iso(auth.issued_at),
        "expires_at": _iso(auth.expires_at),
        "consumed_at": _iso(auth.consumed_at),
        "revoked_at": _iso(auth.revoked_at),
    }


def _execution_result_view(
    result: Optional[ExternalExecutionResult],
) -> Optional[dict[str, Any]]:
    if result is None:
        return None
    return {
        "external_execution_result_id": result.id,
        "execution_authorization_id": result.execution_authorization_id,
        "status": result.status,
        "adapter": result.adapter,
        "external_reference": result.external_reference,
        "settlement_chain": result.settlement_chain,
        "error": result.error,
        "executed_at": _iso(result.executed_at),
    }


def _aiproof_view(proof) -> Optional[dict[str, Any]]:
    if proof is None:
        return None
    return {
        "aiproof_id": proof.id,
        "governed_outcome": proof.governed_outcome,
        "status": proof.status,
        "handoff_status": proof.handoff_status,
        "aiproof_hash": proof.aiproof_hash,
        "created_at": _iso(proof.created_at),
    }


def _derive_stage(
    *,
    decision: Optional[Decision],
    approval: Optional[EscalationApproval],
    authorization: Optional[ExecutionAuthorization],
    execution_result: Optional[ExternalExecutionResult],
    aiproof,
) -> str:
    if decision is None:
        return STAGE_STARTED

    if decision.outcome == DecisionOutcome.DENIED.value:
        return STAGE_DENIED

    if decision.outcome == DecisionOutcome.ESCALATED.value:
        if (
            approval is not None
            and approval.decision_id == decision.id
            and approval.status == EscalationApprovalStatus.ACTIVE.value
        ):
            return STAGE_APPROVAL_SUBMITTED
        return STAGE_AWAITING_APPROVAL

    # APPROVED from here on.
    if aiproof is not None:
        return STAGE_PROOF_GENERATED

    if execution_result is not None:
        if execution_result.status == ExecutionResultStatus.FAILED.value:
            return STAGE_EXECUTION_FAILED
        return STAGE_EXECUTED

    if authorization is not None:
        if authorization.status in (
            AuthorizationStatus.ACTIVE.value,
            AuthorizationStatus.CONSUMED.value,
        ):
            return STAGE_ACTION_INTEGRITY_VERIFIED
        if authorization.status == AuthorizationStatus.REVOKED.value:
            return STAGE_EXECUTION_AUTHORIZATION_REVOKED
        if authorization.status == AuthorizationStatus.EXPIRED.value:
            return STAGE_EXECUTION_AUTHORIZATION_EXPIRED
        return STAGE_EXECUTION_AUTHORIZED

    return STAGE_APPROVED


def _build_view(db: Session, organization_id: str, intent: Intent) -> dict[str, Any]:
    org = organization_id

    decision = DecisionRepository(db).current_for_intent(org, intent.id)
    approvals = EscalationApprovalRepository(db).list_for_intent(org, intent.id)
    approval = _latest(approvals)
    authorizations = ExecutionAuthorizationRepository(db).list_for_intent(
        org, intent.id
    )
    authorization = _latest(authorizations)
    execution_result = None
    if authorization is not None:
        results = ExternalExecutionResultRepository(db).list_for_authorization(
            org, authorization.id
        )
        execution_result = _latest(results)
    aiproof = CanonicalAIProofRepository(db).current_for_intent(org, intent.id)

    stage = _derive_stage(
        decision=decision,
        approval=approval,
        authorization=authorization,
        execution_result=execution_result,
        aiproof=aiproof,
    )

    timestamps = [intent.created_at] + [
        r.created_at
        for r in ([decision] + list(approvals) + list(authorizations))
        if r is not None
    ]
    if execution_result is not None:
        timestamps.append(execution_result.created_at)
    if aiproof is not None:
        timestamps.append(aiproof.created_at)

    return {
        "case_id": _case_id(intent),
        "correlation_id": intent.correlation_id,
        "action_id": intent.id,
        "organization_id": org,
        "stage": stage,
        "intent": {
            "intent_id": intent.id,
            "intent_type": intent.intent_type,
            "action": intent.action,
            "actor_id": intent.actor_id,
            "amount_minor": intent.amount_minor,
            "amount_currency": intent.amount_currency,
            "created_at": _iso(intent.created_at),
        },
        "decision": _decision_view(decision),
        "escalation_approval": _escalation_approval_view(approval),
        "execution_authorization": _authorization_view(authorization),
        "execution_result": _execution_result_view(execution_result),
        "aiproof": _aiproof_view(aiproof),
        "downstream": _DOWNSTREAM_NOTE,
        "updated_at": _iso(max(timestamps)) if timestamps else None,
    }


def get_run_state(
    db: Session, organization_id: str, *, correlation_id: str
) -> Optional[dict[str, Any]]:
    """Return the derived run-state view for the intent carrying ``correlation_id``.

    ``None`` when no intent in this tenant carries that correlation id (the
    run hasn't started, or the caller never set one).
    """
    intent = IntentRepository(db).find_one(
        organization_id, correlation_id=correlation_id
    )
    if intent is None:
        return None
    return _build_view(db, organization_id, intent)


def list_run_states(
    db: Session, organization_id: str, *, case_id: str, limit: int = 50
) -> list[dict[str, Any]]:
    """Return one run-state view per distinct correlation id for ``case_id``.

    Most-recently-created intent first. Mirrors the case lookup convention
    in ``app/astra/tools/handlers.py::_intents_for_case`` -- a case is
    identified by ``Intent.parameters["compliidentity_resource_instance"]``,
    not by any Target field.
    """
    intents = IntentRepository(db).list(organization_id, skip=0, limit=1000)
    matched = [i for i in intents if _case_id(i) == case_id]
    matched.sort(key=lambda i: i.created_at, reverse=True)

    seen_correlation_ids: set[str] = set()
    views: list[dict[str, Any]] = []
    for intent in matched:
        key = intent.correlation_id or intent.id
        if key in seen_correlation_ids:
            continue
        seen_correlation_ids.add(key)
        views.append(_build_view(db, organization_id, intent))
        if len(views) >= limit:
            break
    return views
