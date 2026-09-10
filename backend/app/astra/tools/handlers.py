"""The four Astra tool handlers -- read and propose only.

Every handler takes the :class:`~app.astra.context.AstraInvocationContext` as
its first argument (injected by ``dispatch``, never model-supplied) followed by
keyword arguments that exactly match the tool's JSON schema. Every handler
returns a plain JSON-serializable ``dict`` that is fed back to the model as the
``function_call_output``.

None of these execute anything. ``propose_governed_action`` runs the canonical
decision pipeline and returns the resulting decision; issuing an
``ExecutionAuthorization`` and running any execution adapter stay outside this
layer.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from app.astra.context import AstraInvocationContext
from app.astra.errors import ToolValidationError
from app.astra.sentry_screening import run_screening
from app.repositories.canonical import (
    DecisionRepository,
    EvidenceCollectionJobRepository,
    ExecutionAuthorizationRepository,
    IntentRepository,
    NormalizedEvidenceRepository,
    PolicyResolutionRepository,
    TargetRepository,
)
from app.services.canonical import governed_action_service
from app.utils.canonical_enums import (
    DecisionOutcome,
    EnvironmentType,
    IntentType,
    TargetType,
)

_MONETARY_INTENT_TYPES = {IntentType.TRANSFER.value, IntentType.PAYMENT.value}

_ACTION_TYPE_TO_INTENT_TYPE = {
    "transfer": IntentType.TRANSFER,
    "data_access": IntentType.DATA_ACCESS,
    "workflow_action": IntentType.WORKFLOW_ACTION,
}


# --------------------------------------------------------------------------- #
# shared helpers
# --------------------------------------------------------------------------- #
def _require_case(ctx: AstraInvocationContext, tool: str, supplied: str) -> None:
    if supplied != ctx.case_id:
        raise ToolValidationError(
            tool,
            f"case {supplied!r} is out of scope for this session "
            f"(scoped to {ctx.case_id!r})",
        )


def _load(raw: Optional[str], default: Any) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return default


def _intent_params(intent) -> dict[str, Any]:
    params = _load(getattr(intent, "parameters", None), {})
    return params if isinstance(params, dict) else {}


def _intents_for_case(ctx: AstraInvocationContext) -> list[Any]:
    """Intents in the tenant bound to this case via the CompliIdentity instance."""
    intents = IntentRepository(ctx.db).list(
        ctx.organization_id, skip=0, limit=1000
    )
    matched = [
        i
        for i in intents
        if _intent_params(i).get("compliidentity_resource_instance")
        == ctx.case_id
    ]
    matched.sort(key=lambda i: i.created_at, reverse=True)
    return matched


def _latest_resolution_for_case(ctx: AstraInvocationContext) -> Optional[Any]:
    intent_ids = {i.id for i in _intents_for_case(ctx)}
    if not intent_ids:
        return None
    resolutions = [
        r
        for r in PolicyResolutionRepository(ctx.db).list(
            ctx.organization_id, skip=0, limit=1000
        )
        if r.intent_id in intent_ids
    ]
    if not resolutions:
        return None
    resolutions.sort(key=lambda r: r.created_at, reverse=True)
    return resolutions[0]


def _normalized_claims_for_resolution(
    ctx: AstraInvocationContext, resolution_id: str
) -> dict[str, dict[str, Any]]:
    job = EvidenceCollectionJobRepository(ctx.db).latest_for_resolution(
        ctx.organization_id, resolution_id
    )
    if job is None:
        return {}
    by_req: dict[str, dict[str, Any]] = {}
    for norm in NormalizedEvidenceRepository(ctx.db).list_for_job(
        ctx.organization_id, job.id
    ):
        if norm.evidence_requirement_id in by_req:
            continue
        claims = _load(norm.normalized_claims, {})
        by_req[norm.evidence_requirement_id] = (
            claims if isinstance(claims, dict) else {}
        )
    return by_req


def _decision_view(decision) -> dict[str, Any]:
    return {
        "decision_id": decision.id,
        "intent_id": decision.intent_id,
        "outcome": decision.outcome,
        "reason_codes": _load(decision.reason_codes, []),
        "authority_status": decision.authority_status,
        "authority_reason": decision.authority_reason,
        "required_approver_types": _load(decision.required_approver_types, []),
        "supersession_status": decision.supersession_status,
        "prior_decision_id": decision.prior_decision_id,
        "superseded_by_decision_id": decision.superseded_by_decision_id,
        "decided_at": _iso(decision.decided_at),
        "decision_hash": decision.decision_hash,
    }


def _iso(value) -> Optional[str]:
    return value.isoformat() if value is not None else None


# --------------------------------------------------------------------------- #
# get_case_data
# --------------------------------------------------------------------------- #
def get_case_data(
    ctx: AstraInvocationContext,
    *,
    case_id: str,
    sections: Optional[list[str]] = None,
) -> dict[str, Any]:
    _require_case(ctx, "get_case_data", case_id)
    wanted = set(sections or ["case", "kyc", "counterparties", "recent_decisions"])

    case_intents = _intents_for_case(ctx)
    resolution = _latest_resolution_for_case(ctx)
    claims_by_req = (
        _normalized_claims_for_resolution(ctx, resolution.id)
        if resolution is not None
        else {}
    )

    out: dict[str, Any] = {"case_id": case_id}

    if "case" in wanted:
        targets = [
            {
                "target_id": t.id,
                "target_type": t.target_type,
                "external_identifier": t.external_identifier,
                "trust_status": t.trust_status,
                "owner": t.owner,
                "classification": t.classification,
            }
            for t in TargetRepository(ctx.db).list(
                ctx.organization_id, skip=0, limit=1000
            )
            if t.external_identifier == case_id
        ]
        out["case"] = {
            "case_id": case_id,
            "organization_id": ctx.organization_id,
            "targets": targets,
            "intent_count": len(case_intents),
            "latest_policy_resolution_id": (
                resolution.id if resolution is not None else None
            ),
        }

    if "kyc" in wanted:
        # The closest thing to KYC/screening state that exists as a canonical
        # record: the validated, normalized evidence claims for the case's
        # most recent resolution, keyed by evidence-requirement id.
        out["kyc"] = {
            "source": "normalized_evidence",
            "policy_resolution_id": (
                resolution.id if resolution is not None else None
            ),
            "evidence_claims": claims_by_req,
        }

    if "counterparties" in wanted:
        seen: dict[str, dict[str, Any]] = {}
        for intent in case_intents:
            params = _intent_params(intent)
            counterparty = params.get("counterparty") or params.get(
                "counterparty_id"
            )
            if not counterparty or counterparty in seen:
                continue
            seen[counterparty] = {"counterparty_id": counterparty}
        # Attach any screening result whose subject matches a counterparty.
        for claims in claims_by_req.values():
            subject = (claims.get("subject") or {}).get("id")
            if subject in seen and "result" in claims:
                seen[subject]["latest_screening"] = {
                    "result": claims.get("result"),
                    "risk_level": claims.get("risk_level"),
                    "requires_human_review": claims.get(
                        "requires_human_review"
                    ),
                    "screened_at": claims.get("screened_at"),
                    "simulation": claims.get("simulation"),
                }
        out["counterparties"] = list(seen.values())

    if "recent_decisions" in wanted:
        views: list[dict[str, Any]] = []
        for intent in case_intents:
            for decision in DecisionRepository(ctx.db).list_for_intent(
                ctx.organization_id, intent.id, skip=0, limit=100
            ):
                views.append(_decision_view(decision))
        views.sort(key=lambda v: v["decided_at"] or "", reverse=True)
        out["recent_decisions"] = views

    return out


# --------------------------------------------------------------------------- #
# get_authorized_transaction_history
# --------------------------------------------------------------------------- #
def get_authorized_transaction_history(
    ctx: AstraInvocationContext,
    *,
    case_id: str,
    limit: int = 50,
    direction: Optional[str] = None,
) -> dict[str, Any]:
    _require_case(ctx, "get_authorized_transaction_history", case_id)
    limit = max(1, min(int(limit), 200))

    records: list[dict[str, Any]] = []
    for intent in _intents_for_case(ctx):
        if intent.intent_type not in _MONETARY_INTENT_TYPES:
            continue
        params = _intent_params(intent)
        if direction and params.get("direction") not in (None, direction):
            continue

        decision = DecisionRepository(ctx.db).current_for_intent(
            ctx.organization_id, intent.id
        )
        if decision is None or decision.outcome != DecisionOutcome.APPROVED.value:
            continue

        authorizations = ExecutionAuthorizationRepository(
            ctx.db
        ).list_for_intent(ctx.organization_id, intent.id, skip=0, limit=10)

        records.append(
            {
                "intent_id": intent.id,
                "action": intent.action,
                "intent_type": intent.intent_type,
                "amount_minor": intent.amount_minor,
                "amount_currency": intent.amount_currency,
                "counterparty": params.get("counterparty")
                or params.get("counterparty_id"),
                "direction": params.get("direction"),
                "decision_id": decision.id,
                "decision_outcome": decision.outcome,
                "decided_at": _iso(decision.decided_at),
                "execution_authorization_ids": [a.id for a in authorizations],
                "authorized": bool(authorizations),
                "created_at": _iso(intent.created_at),
            }
        )

    records.sort(key=lambda r: r["created_at"] or "", reverse=True)
    return {
        "case_id": case_id,
        "direction_filter": direction,
        "count": len(records[:limit]),
        "transactions": records[:limit],
    }


# --------------------------------------------------------------------------- #
# request_sanctions_screening
# --------------------------------------------------------------------------- #
def request_sanctions_screening(
    ctx: AstraInvocationContext,
    *,
    subject_id: str,
    subject_type: str = "wallet",
    reason: Optional[str] = None,
) -> dict[str, Any]:
    if not (subject_id or "").strip():
        raise ToolValidationError(
            "request_sanctions_screening", "subject_id must be non-empty"
        )
    return run_screening(
        ctx.db,
        organization_id=ctx.organization_id,
        case_id=ctx.case_id,
        correlation_id=ctx.correlation_id,
        subject_id=subject_id,
        subject_type=subject_type,
        reason=reason,
    )


# --------------------------------------------------------------------------- #
# propose_governed_action  (AIRA's terminal action)
# --------------------------------------------------------------------------- #
def propose_governed_action(
    ctx: AstraInvocationContext,
    *,
    action_type: str,
    compliidentity_resource: str,
    compliidentity_action: str,
    resource_instance: str,
    rationale: str,
    target_identifier: Optional[str] = None,
    amount_minor: Optional[int] = None,
    amount_currency: Optional[str] = None,
    parameters: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    tool = "propose_governed_action"
    _require_case(ctx, tool, resource_instance)

    intent_type = _ACTION_TYPE_TO_INTENT_TYPE.get(action_type)
    if intent_type is None:
        raise ToolValidationError(
            tool, f"unsupported action_type {action_type!r}"
        )
    if compliidentity_action not in ("propose", "read"):
        raise ToolValidationError(
            tool,
            f"compliidentity_action {compliidentity_action!r} is not available "
            "to the model (only 'propose' / 'read')",
        )
    if amount_minor is not None and amount_minor < 0:
        raise ToolValidationError(tool, "amount_minor must be >= 0")
    if amount_minor is not None and not amount_currency:
        raise ToolValidationError(
            tool, "amount_currency is required when amount_minor is set"
        )

    # Flatten the bounded ``parameters`` object into intent parameters, and
    # derive ``counterparty`` from ``target_identifier`` so the read tools
    # (get_authorized_transaction_history / get_case_data counterparties) can
    # key off it later.
    extra: dict[str, Any] = {}
    for key in ("direction", "note"):
        value = (parameters or {}).get(key)
        if value is not None:
            extra[key] = value
    if target_identifier:
        extra.setdefault("counterparty", target_identifier)

    result = governed_action_service.propose(
        ctx.db,
        ctx.organization_id,
        actor_id=ctx.actor_id,
        intent_type=intent_type,
        action=f"astra_{action_type}",
        compliidentity_resource=compliidentity_resource,
        compliidentity_action=compliidentity_action,
        resource_instance=resource_instance,
        target_identifier=target_identifier,
        rationale=rationale,
        amount_minor=amount_minor,
        amount_currency=amount_currency,
        target_type=TargetType.TRANSACTION,
        environment=EnvironmentType.STAGING,
        extra_parameters=extra or None,
        correlation_id=ctx.correlation_id,
    )

    decision = result.decision
    outcome = decision.outcome
    next_step = {
        DecisionOutcome.APPROVED.value: (
            "authorization_issuable: the application may now issue an "
            "ExecutionAuthorization for this decision. You do not do this."
        ),
        DecisionOutcome.DENIED.value: "blocked: the action is denied and cannot proceed.",
        DecisionOutcome.ESCALATED.value: (
            "human_approval_required: an authorized human approver must submit "
            "an escalation approval (POST /api/v1/escalation-approvals, then "
            "/apply) before this can proceed. You cannot approve it."
        ),
    }.get(outcome, "unknown")

    return {
        "proposed": True,
        "terminal": True,
        "intent_id": result.intent.id,
        "policy_resolution_id": result.policy_resolution.id,
        "assessment_result": (
            result.assessment.overall_result
            if result.assessment is not None
            else None
        ),
        "decision": _decision_view(decision),
        "outcome": outcome,
        "next_step": next_step,
    }
