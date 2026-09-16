"""CompliLedger Demo #3 -- Fix Order step 2: CompliAGL decision scenarios
against a LIVE CompliIdentity instance.

Every prior CompliAGL test of this integration uses a fake authority-context
client (monkeypatched ``AuthorityContext`` values). This driver runs the
real deterministic decision pipeline
(intent -> resolution -> applicability -> evidence -> assessment -> decision)
in-process, with ``authority_context_service`` making **real HTTP calls** to
the CompliIdentity instance on ``COMPLIIDENTITY_BASE_URL`` (default
``http://127.0.0.1:8137``, the ``compliidentity_demo3_step2.db`` instance
created by ``compliidentity_setup_phases_1_7.py``).

Scenarios (Fix Order step 2 acceptance criteria 4a / 4b / 4c / 4d / 4e / 4f):

    4a  SENTRY attempts aml.case:read outside its delegated scope   -> DENIED
    4b  AIRA proposes a $250,000 action                             -> ESCALATED
    4c  Jordan approves the escalation -> CompliAGL re-evaluates     -> APPROVED
        (first ESCALATED decision preserved + SUPERSEDED, new APPROVED
        decision, approval CONSUMED, ExecutionAuthorization then issues).
        4c-neg-wrong-approver   SENTRY (no approve grant) is rejected
        4c-neg-expired-approval an expired approval does not upgrade
    4d  wrong actor / wrong action / wrong instance (3 combos)       -> not APPROVED
    4e  no ExecutionAuthorization is issued for any DENIED/ESCALATED decision
    4f  4c's APPROVED decision's ExecutionAuthorization is verified, consumed,
        an external execution result is recorded, and a canonical AIProof is
        generated, signed, and independently re-verified -- the second half of
        the chain (APPROVED -> authorization -> AIProof) this driver never
        exercised before.

===================================================================
SANCTIONS SCREENING -- READ THIS
===================================================================
Every scenario below registers the **real** SENTRY sanctions-screening
connector (``harborstone_sentry_screening_connector``, ``is_mock=False`` --
see ``backend/app/services/evidence/connectors/harborstone_sentry_screening.py``),
the same one CompliAGL registers by default in production. Every scenario's
resource_instance is a case id, not a wallet id, so the connector resolves an
unknown screening subject -> ``NO_MATCH`` -> ``CTL-HARBORSTONE-SANCTIONS-
SCREENING`` SATISFIED; the decision outcome below 4d/4e is driven purely by
the *authority-context wiring* (4a/4b/4d), not by an evidence gap. What is
still simulated is only the screening *lookup* itself (a small deterministic
dataset, not a real OFAC/vendor call) -- see that connector's own docstring
for the ``claims.simulation=True`` disclosure. This replaces the retired
``CTL-PLACEHOLDER-SANCTIONS-SCREENING`` stand-in this driver used through
2026-09-10 (before the real connector existed).

**These results prove the CompliIdentity authority integration, the
decision-engine wiring, and (as of 4f) the post-APPROVED authorization ->
AIProof chain, all against a live CompliIdentity instance. They do NOT prove
that a real (non-simulated) sanctions-list lookup works.**
Every scenario below carries an explicit ``proves`` / ``does_NOT_prove``.

Run:
    # CompliIdentity must be up (separate terminal, CompliIdentity repo):
    #   $env:DATABASE_URL="sqlite:///./compliidentity_demo3_step2_live.db"
    #   python -m uvicorn compliidentity.bootstrap:create_app --factory --port 8137
    backend/venv/Scripts/python.exe demo3_step2/compliidentity_setup_phases_1_7.py
    backend/venv/Scripts/python.exe demo3_step2/compliagl_scenarios.py
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

# --- make the CompliAGL backend package importable regardless of cwd ------ #
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_BACKEND = os.path.join(_REPO_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

# --- environment MUST be set before importing any app module -------------- #
_DEMO_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "compliagl_demo3.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_DEMO_DB}"
os.environ["DEBUG"] = "false"

# COMPLIIDENTITY_BASE_URL / COMPLIIDENTITY_SERVICE_PRINCIPAL_ID -- the live
# authority-context wiring default_client() reads from os.environ. Single source
# of truth for these values; importing it applies them (setdefault).
import _live_env  # noqa: E402,F401

# a fresh db per run keeps the captured evidence reproducible
if os.path.exists(_DEMO_DB):
    os.remove(_DEMO_DB)

import logging  # noqa: E402

logging.disable(logging.WARNING)

from app.core.database import SessionLocal  # noqa: E402
from app.db import seed  # noqa: E402
from app.db.init_db import init_db  # noqa: E402
from app.db.seed import (  # noqa: E402
    HARBORSTONE_AIRA_ACTOR_ID,
    HARBORSTONE_JORDAN_ACTOR_ID,
    HARBORSTONE_ORG_ID,
    HARBORSTONE_SENTRY_ACTOR_ID,
)
from app.schemas.canonical.intent import IntentCreate  # noqa: E402
from app.schemas.canonical.operational_context import (  # noqa: E402
    OperationalContextCreate,
)
from app.schemas.canonical.policy_applicability import (  # noqa: E402
    ApplicabilityEvaluationCreate,
    PolicyResolutionCreate,
)
from app.schemas.canonical.aiproof import (  # noqa: E402
    ActorIdentityRef,
    DecisionRef,
    ExecutionAuthorizationRef,
    ExternalExecutionResultRef,
    GovernedOutcome,
    IntentRef,
    ProofMetadata,
    ProofTimestamps,
)
from app.schemas.canonical.governance import ExternalExecutionResultCreate  # noqa: E402
from app.schemas.canonical.target import TargetCreate  # noqa: E402
from app.services.canonical import (  # noqa: E402
    applicability_service,
    assessment_service,
    authority_context_service,
    authorization_service,
    control_evaluation_service,
    decision_service,
    escalation_approval_service,
    evidence_sufficiency_service,
    governance_service,
    intent_service,
    operational_context_service,
    policy_resolution_service,
    target_service,
)
from app.services.canonical.aiproof import generator as aiproof_generator  # noqa: E402
from app.services.canonical.aiproof import service as aiproof_service  # noqa: E402
from app.services.canonical.aiproof.verify import verify_aiproof  # noqa: E402
from app.services.canonical.errors import (  # noqa: E402
    AuthorityVerificationError,
    ConflictError,
)
from app.services.evidence import evidence_collection_service  # noqa: E402
from app.services.evidence.connectors import ConnectorRegistry  # noqa: E402
from app.services.evidence.connectors.harborstone_sentry_screening import (  # noqa: E402
    harborstone_sentry_screening_connector,
)
from app.utils.canonical_enums import (  # noqa: E402
    ExecutionResultStatus,
    IntentType,
    TargetType,
)

CASE = "HARBORSTONE-2024-0042"
OTHER_CASE = "OTHER-CASE-0001"

_RESULTS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "compliagl_scenarios_results.json"
)


# --------------------------------------------------------------------------- #
# Capture real CompliIdentity HTTP traffic made during decide_for_resolution
# --------------------------------------------------------------------------- #
_AUTHORITY_CALLS: list[dict] = []
_real_default_client = authority_context_service.default_client


def _capturing_default_client(**kwargs):
    client = _real_default_client(**kwargs)
    if client is None:
        _AUTHORITY_CALLS.append({"error": "default_client() returned None (unconfigured)"})
        return None
    real_fetch = client.fetch

    def fetch(**fkw):
        result = real_fetch(**fkw)
        _AUTHORITY_CALLS.append(
            {
                "request": fkw,
                "authority_status": result.status,
                "authority_reason": result.reason,
                "sufficient": result.sufficient,
                "permission_present": result.permission_present,
                "approval_required": result.approval_required,
                "limit_exceeded": result.limit_exceeded,
                "findings": list(result.findings),
                "authority_revision": result.authority_revision,
                "integrity_content_hash": result.integrity_content_hash,
                "raw_response": result.raw,
            }
        )
        return result

    client.fetch = fetch
    return client


authority_context_service.default_client = _capturing_default_client


# --------------------------------------------------------------------------- #
# One decision pipeline run
# --------------------------------------------------------------------------- #
def run_pipeline(
    db,
    *,
    actor_id: str,
    intent_type: IntentType,
    action: str,
    ci_resource: str,
    ci_action: str,
    resource_instance: str,
    amount_minor: int | None = None,
):
    _AUTHORITY_CALLS.clear()
    intent = intent_service.create(
        db,
        IntentCreate(
            organization_id=HARBORSTONE_ORG_ID,
            intent_type=intent_type,
            action=action,
            actor_id=actor_id,
            amount_minor=amount_minor,
            amount_currency="USD" if amount_minor is not None else None,
            parameters={
                "compliidentity_resource": ci_resource,
                "compliidentity_action": ci_action,
                "compliidentity_resource_instance": resource_instance,
            },
        ),
    )
    target = target_service.create(
        db,
        TargetCreate(
            organization_id=HARBORSTONE_ORG_ID,
            target_type=TargetType.TRANSACTION,
            external_identifier=resource_instance,
        ),
    )
    context = operational_context_service.create(
        db,
        OperationalContextCreate(
            organization_id=HARBORSTONE_ORG_ID,
            jurisdiction="US",
            environment="STAGING",
        ),
    )
    resolution = policy_resolution_service.resolve(
        db,
        PolicyResolutionCreate(
            organization_id=HARBORSTONE_ORG_ID,
            actor_identity_id=actor_id,
            intent_id=intent.id,
            target_id=target.id,
            operational_context_id=context.id,
        ),
    )
    applicability_service.evaluate_for_resolution(
        db,
        ApplicabilityEvaluationCreate(
            organization_id=HARBORSTONE_ORG_ID, policy_resolution_id=resolution.id
        ),
    )
    evidence_collection_service.start_collection(
        db,
        HARBORSTONE_ORG_ID,
        resolution.id,
        production_mode=False,
        registry=ConnectorRegistry([harborstone_sentry_screening_connector()]),
    )
    evidence_sufficiency_service.evaluate_for_resolution(
        db, HARBORSTONE_ORG_ID, resolution.id
    )
    control_evaluation_service.evaluate_for_resolution(
        db, HARBORSTONE_ORG_ID, resolution.id
    )
    assessment = assessment_service.assess_for_resolution(
        db, HARBORSTONE_ORG_ID, resolution.id
    )
    decision = decision_service.decide_for_resolution(
        db, HARBORSTONE_ORG_ID, resolution.id
    )
    return {
        "intent_id": intent.id,
        "resolution_id": resolution.id,
        "assessment_result": assessment.overall_result,
        "decision": decision,
        "compliidentity_calls": list(_AUTHORITY_CALLS),
    }


def _decision_view(decision) -> dict:
    return {
        "decision_id": decision.id,
        "outcome": decision.outcome,
        "reason_codes": json.loads(decision.reason_codes or "[]"),
        "decision_conditions_triggered": json.loads(
            decision.decision_conditions_triggered or "[]"
        ),
        "authority_status": decision.authority_status,
        "authority_reason": decision.authority_reason,
        "required_approver_types": json.loads(
            decision.required_approver_types or "[]"
        ),
        "input_hash": decision.input_hash,
        "decision_hash": decision.decision_hash,
        "approval_hash": decision.approval_hash,
        "prior_decision_id": decision.prior_decision_id,
        "superseded_by_decision_id": decision.superseded_by_decision_id,
        "supersession_status": decision.supersession_status,
    }


def _try_issue_authorization(db, decision_id: str) -> dict:
    """4e: an ExecutionAuthorization must NOT be issuable for a non-APPROVED
    decision."""
    try:
        auth = authorization_service.issue(db, HARBORSTONE_ORG_ID, decision_id)
        return {
            "issued": True,
            "authorization_id": auth.id,
            "VIOLATION": "an authorization was issued for a non-APPROVED decision",
        }
    except ConflictError as exc:
        return {"issued": False, "raised": "ConflictError", "message": str(exc)}


# --------------------------------------------------------------------------- #
# Scenarios
# --------------------------------------------------------------------------- #
def main() -> int:
    init_db()
    db = SessionLocal()
    seed.seed_organizations(db)
    seed.seed_harborstone_actors(db)
    seed.seed_harborstone_package(db)

    principals = {
        "aira": seed._HARBORSTONE_AIRA_PRINCIPAL_ID,
        "sentry": seed._HARBORSTONE_SENTRY_PRINCIPAL_ID,
        "jordan": seed._HARBORSTONE_JORDAN_PRINCIPAL_ID,
    }

    scenarios: list[dict] = []

    # --- 4a ------------------------------------------------------------- #
    r = run_pipeline(
        db,
        actor_id=HARBORSTONE_SENTRY_ACTOR_ID,
        intent_type=IntentType.DATA_ACCESS,
        action="read_case_file",
        ci_resource="aml.case",
        ci_action="read",
        resource_instance=CASE,
    )
    d = r["decision"]
    scenarios.append(
        {
            "id": "4a",
            "title": "SENTRY attempts aml.case:read outside its delegated scope",
            "proves": (
                "CompliIdentity reports the delegate has no permission for this "
                "resource, and CompliAGL's DC-HARBORSTONE-AUTHORITY-DENIED "
                "condition turns that into a terminal DENIED -- overriding an "
                "otherwise-SATISFIED assessment"
            ),
            "does_NOT_prove": (
                "a real (non-simulated) sanctions-list lookup -- the "
                "screening subject resolves to an unknown id (the case, not "
                "a wallet), so it's always NO_MATCH regardless of a real hit"
            ),
            "actor": "sentry",
            "compliidentity": {
                "resource": "aml.case",
                "action": "read",
                "resource_instance": CASE,
            },
            "expected": {"outcome": "DENIED", "reason_code": "AUTHORITY_DENIED"},
            "assessment_result": r["assessment_result"],
            "decision": _decision_view(d),
            "no_execution_authorization": _try_issue_authorization(db, d.id),
            "compliidentity_calls": r["compliidentity_calls"],
            "PASS": d.outcome == "DENIED"
            and "AUTHORITY_DENIED" in json.loads(d.reason_codes or "[]"),
        }
    )

    # --- 4b ------------------------------------------------------------- #
    r = run_pipeline(
        db,
        actor_id=HARBORSTONE_AIRA_ACTOR_ID,
        intent_type=IntentType.TRANSFER,
        action="propose_transfer",
        ci_resource="aml.action",
        ci_action="propose",
        resource_instance=CASE,
        amount_minor=25_000_000,
    )
    d = r["decision"]
    scenarios.append(
        {
            "id": "4b",
            "title": "AIRA proposes a $250,000.00 action",
            "proves": (
                "CompliIdentity reports approval_required:true at exactly the "
                "$250,000.00 threshold; CompliAGL's DC-HARBORSTONE-HUMAN-APPROVAL "
                "condition turns that into ESCALATED / HUMAN_APPROVAL_REQUIRED. "
                "The assessment is SATISFIED, so the escalation comes from the "
                "authority-context wiring, not an evidence gap"
            ),
            "does_NOT_prove": (
                "a real (non-simulated) sanctions-list lookup -- the "
                "screening subject resolves to an unknown id (the case, not "
                "a wallet), so it's always NO_MATCH regardless of a real hit"
            ),
            "actor": "aira",
            "compliidentity": {
                "resource": "aml.action",
                "action": "propose",
                "attribute": "amount",
                "value": "25000000",
                "resource_instance": CASE,
            },
            "expected": {
                "outcome": "ESCALATED",
                "reason_code": "HUMAN_APPROVAL_REQUIRED",
            },
            "assessment_result": r["assessment_result"],
            "decision": _decision_view(d),
            "no_execution_authorization": _try_issue_authorization(db, d.id),
            "compliidentity_calls": r["compliidentity_calls"],
            "PASS": d.outcome == "ESCALATED"
            and "HUMAN_APPROVAL_REQUIRED" in json.loads(d.reason_codes or "[]"),
        }
    )

    # --- 4c: Jordan approves the escalation -> re-evaluate -> APPROVED - #
    def _propose_250k():
        return run_pipeline(
            db,
            actor_id=HARBORSTONE_AIRA_ACTOR_ID,
            intent_type=IntentType.TRANSFER,
            action="propose_transfer",
            ci_resource="aml.action",
            ci_action="propose",
            resource_instance=CASE,
            amount_minor=25_000_000,
        )

    r = _propose_250k()
    d1 = r["decision"]
    first_calls = list(r["compliidentity_calls"])
    _AUTHORITY_CALLS.clear()
    approval = escalation_approval_service.submit(
        db,
        HARBORSTONE_ORG_ID,
        decision_id=d1.id,
        approver_principal_id=seed._HARBORSTONE_JORDAN_PRINCIPAL_ID,
        rationale=(
            "Jordan Lee reviewed HARBORSTONE-2024-0042 and approves the "
            "$250,000.00 action."
        ),
    )
    approver_calls = list(_AUTHORITY_CALLS)
    _AUTHORITY_CALLS.clear()
    d2 = decision_service.decide_for_resolution(
        db, HARBORSTONE_ORG_ID, r["resolution_id"], prior_decision_id=d1.id
    )
    redecide_calls = list(_AUTHORITY_CALLS)
    d1_after = decision_service.get(db, HARBORSTONE_ORG_ID, d1.id)
    approval_after = escalation_approval_service.get(
        db, HARBORSTONE_ORG_ID, approval.id
    )
    auth_before = _try_issue_authorization(db, d1.id)  # ESCALATED -> rejected
    auth_after = authorization_service.issue(db, HARBORSTONE_ORG_ID, d2.id)
    required_types = json.loads(d1.required_approver_types or "[]")
    scenarios.append(
        {
            "id": "4c",
            "title": (
                "Jordan approves the escalated decision; CompliAGL "
                "re-evaluates to APPROVED, first decision preserved"
            ),
            "proves": (
                "escalation_approval_service.submit() verifies Jordan's "
                "authority to approve LIVE against CompliIdentity (real "
                "aml.action:approve probe -> sufficient:true, HUMAN principal, "
                "matching Decision.required_approver_types distilled from "
                "CompliIdentity's own applicable_approvals on AIRA's probe); "
                "then decide_for_resolution(prior_decision_id=) upgrades the "
                "escalation via DC-HARBORSTONE-APPROVED-VIA-HUMAN. The prior "
                "ESCALATED decision is preserved + SUPERSEDED, a NEW APPROVED "
                "decision is created, the approval is CONSUMED, and only then "
                "does an ExecutionAuthorization issue."
            ),
            "does_NOT_prove": (
                "a real (non-simulated) sanctions-list lookup -- the "
                "screening subject resolves to an unknown id (the case, not "
                "a wallet), so it's always NO_MATCH regardless of a real hit"
            ),
            "actor": "jordan",
            "compliidentity": {
                "resource": "aml.action",
                "action": "approve",
                "resource_instance": CASE,
                "approver_principal_id": seed._HARBORSTONE_JORDAN_PRINCIPAL_ID,
            },
            "expected": {"outcome": "APPROVED", "first_decision_preserved": True},
            "required_approver_types_on_first_decision": required_types,
            "first_decision": _decision_view(d1),
            "escalation_approval": {
                "escalation_approval_id": approval.escalation_approval_id,
                "approver_principal_id": approval.approver_principal_id,
                "approver_principal_type": approval.approver_principal_type,
                "approver_authority_hash": approval.approver_authority_hash,
                "valid_until": approval.valid_until,
                "status_after_reevaluation": approval_after.status,
                "consumed_by_decision_id": approval_after.consumed_by_decision_id,
            },
            "reevaluated_decision": _decision_view(d2),
            "first_decision_after_reevaluation": _decision_view(d1_after),
            "no_execution_authorization": auth_before,
            "execution_authorization_after_approval": {
                "issued": True,
                "authorization_id": auth_after.id,
                "decision_id": auth_after.decision_id,
            },
            "compliidentity_calls": {
                "first_decision": first_calls,
                "approver_probe": approver_calls,
                "reevaluation": redecide_calls,
            },
            "PASS": (
                d2.outcome == "APPROVED"
                and d2.id != d1.id
                and d2.prior_decision_id == d1.id
                and d1_after.supersession_status == "SUPERSEDED"
                and d1_after.superseded_by_decision_id == d2.id
                and approval_after.status == "CONSUMED"
                and approval_after.consumed_by_decision_id == d2.id
                and auth_before.get("issued") is False
                and auth_after.decision_id == d2.id
                and required_types == ["HUMAN"]
            ),
        }
    )

    # --- 4c-neg-wrong-approver: no aml.action:approve grant ----------- #
    r = _propose_250k()
    d1n = r["decision"]
    _AUTHORITY_CALLS.clear()
    try:
        escalation_approval_service.submit(
            db,
            HARBORSTONE_ORG_ID,
            decision_id=d1n.id,
            approver_principal_id=seed._HARBORSTONE_SENTRY_PRINCIPAL_ID,
            rationale=(
                "SENTRY (screening agent, holds no approve authority) "
                "attempts to approve"
            ),
        )
        rejected = {
            "rejected": False,
            "VIOLATION": "an unauthorized approver was accepted",
        }
    except AuthorityVerificationError as exc:
        rejected = {"rejected": True, "reason": exc.reason, "message": str(exc)}
    approver_calls = list(_AUTHORITY_CALLS)
    scenarios.append(
        {
            "id": "4c-neg-wrong-approver",
            "title": "an approver without aml.action:approve authority is rejected",
            "proves": (
                "submit() rejects SENTRY -- CompliIdentity reports "
                "sufficient:false for SENTRY on aml.action:approve -- no "
                "EscalationApproval is recorded and the decision stays ESCALATED"
            ),
            "does_NOT_prove": (
                "a real (non-simulated) sanctions-list lookup (see the "
                "connector's own claims.simulation disclosure)"
            ),
            "actor": "sentry",
            "compliidentity": {
                "resource": "aml.action",
                "action": "approve",
                "resource_instance": CASE,
                "approver_principal_id": seed._HARBORSTONE_SENTRY_PRINCIPAL_ID,
            },
            "expected": {"approval_rejected": True, "decision_still": "ESCALATED"},
            "first_decision": _decision_view(d1n),
            "approval_attempt": rejected,
            "no_execution_authorization": _try_issue_authorization(db, d1n.id),
            "compliidentity_calls": {"approver_probe": approver_calls},
            "PASS": (
                rejected.get("rejected") is True
                and d1n.outcome == "ESCALATED"
                and not escalation_approval_service.list_for_decision(
                    db, HARBORSTONE_ORG_ID, d1n.id
                )
            ),
        }
    )

    # --- 4c-neg-expired-approval: a closed window -> not APPROVED ------ #
    r = _propose_250k()
    d1e = r["decision"]
    _AUTHORITY_CALLS.clear()
    expired_approval = escalation_approval_service.submit(
        db,
        HARBORSTONE_ORG_ID,
        decision_id=d1e.id,
        approver_principal_id=seed._HARBORSTONE_JORDAN_PRINCIPAL_ID,
        rationale="Jordan approves, but the approval window has already closed",
        valid_until=datetime.now(timezone.utc) - timedelta(seconds=1),
    )
    approver_calls = list(_AUTHORITY_CALLS)
    _AUTHORITY_CALLS.clear()
    d2e = decision_service.decide_for_resolution(
        db, HARBORSTONE_ORG_ID, r["resolution_id"], prior_decision_id=d1e.id
    )
    expired_after = escalation_approval_service.get(
        db, HARBORSTONE_ORG_ID, expired_approval.id
    )
    scenarios.append(
        {
            "id": "4c-neg-expired-approval",
            "title": "an expired approval does not upgrade the escalation",
            "proves": (
                "the approval is authority-verified and recorded, but "
                "approval.expired is true at re-decision time, so "
                "DC-HARBORSTONE-APPROVED-VIA-HUMAN does not fire -- the "
                "re-decision is still ESCALATED and the approval is not consumed"
            ),
            "does_NOT_prove": (
                "a real (non-simulated) sanctions-list lookup (see the "
                "connector's own claims.simulation disclosure)"
            ),
            "actor": "jordan",
            "compliidentity": {
                "resource": "aml.action",
                "action": "approve",
                "resource_instance": CASE,
            },
            "expected": {
                "reevaluation_outcome": "ESCALATED",
                "approval_consumed": False,
            },
            "first_decision": _decision_view(d1e),
            "escalation_approval": {
                "escalation_approval_id": expired_approval.escalation_approval_id,
                "valid_until": expired_approval.valid_until,
                "status_after_reevaluation": expired_after.status,
                "consumed_by_decision_id": expired_after.consumed_by_decision_id,
            },
            "reevaluated_decision": _decision_view(d2e),
            "no_execution_authorization": _try_issue_authorization(db, d2e.id),
            "compliidentity_calls": {"approver_probe": approver_calls},
            "PASS": (
                d2e.outcome == "ESCALATED"
                and expired_after.status == "ACTIVE"
                and expired_after.consumed_by_decision_id is None
            ),
        }
    )

    # --- 4d: wrong actor / wrong action / wrong instance --------------- #
    d4d = [
        (
            "4d-i",
            "wrong actor: SENTRY attempts aml.action:propose (it has no such grant)",
            HARBORSTONE_SENTRY_ACTOR_ID,
            "sentry",
            IntentType.TRANSFER,
            "propose_transfer",
            "aml.action",
            "propose",
            CASE,
            None,
        ),
        (
            "4d-ii",
            "wrong action: AIRA attempts aml.action:approve (Jordan's action)",
            HARBORSTONE_AIRA_ACTOR_ID,
            "aira",
            IntentType.WORKFLOW_ACTION,
            "approve_transfer",
            "aml.action",
            "approve",
            CASE,
            None,
        ),
        (
            "4d-iii",
            "wrong instance: AIRA proposes on OTHER-CASE-0001 (grant scoped to "
            "HARBORSTONE-2024-0042)",
            HARBORSTONE_AIRA_ACTOR_ID,
            "aira",
            IntentType.TRANSFER,
            "propose_transfer",
            "aml.action",
            "propose",
            OTHER_CASE,
            25_000_000,
        ),
    ]
    for (
        sid,
        title,
        actor_id,
        actor_name,
        itype,
        action,
        ci_res,
        ci_act,
        inst,
        amount,
    ) in d4d:
        r = run_pipeline(
            db,
            actor_id=actor_id,
            intent_type=itype,
            action=action,
            ci_resource=ci_res,
            ci_action=ci_act,
            resource_instance=inst,
            amount_minor=amount,
        )
        d = r["decision"]
        scenarios.append(
            {
                "id": sid,
                "title": title,
                "proves": (
                    "a wrong actor / wrong action / wrong resource_instance is "
                    "reported by CompliIdentity as insufficient authority and "
                    "never reaches APPROVED"
                ),
                "does_NOT_prove": (
                    "a real (non-simulated) sanctions-list lookup (see the "
                "connector's own claims.simulation disclosure)"
                ),
                "actor": actor_name,
                "compliidentity": {
                    "resource": ci_res,
                    "action": ci_act,
                    "resource_instance": inst,
                },
                "expected": {"outcome_not": "APPROVED"},
                "assessment_result": r["assessment_result"],
                "decision": _decision_view(d),
                "no_execution_authorization": _try_issue_authorization(db, d.id),
                "compliidentity_calls": r["compliidentity_calls"],
                "PASS": d.outcome != "APPROVED",
            }
        )

    # --- 4f: 4c's APPROVED decision -> authorization -> AIProof -------- #
    # Everything from here on is CompliAGL-internal (no further CompliIdentity
    # calls) but chains directly off d2/auth_after -- the real, live-verified
    # APPROVED decision and the authorization issued for it in scenario 4c.
    d2_intent = intent_service.get(db, HARBORSTONE_ORG_ID, d2.intent_id)
    verify_result = authorization_service.verify(db, HARBORSTONE_ORG_ID, auth_after.id)
    execution_result = governance_service.create_execution_result(
        db,
        ExternalExecutionResultCreate(
            organization_id=HARBORSTONE_ORG_ID,
            execution_authorization_id=auth_after.id,
            intent_id=d2.intent_id,
            adapter="hedera",
            status=ExecutionResultStatus.CONFIRMED,
            external_reference="0.0.123456@1700000000.000000000",
            settlement_chain="hedera-testnet",
        ),
    )
    try:
        consumed_auth = authorization_service.consume(db, HARBORSTONE_ORG_ID, auth_after.id)
        replay = authorization_service.consume(db, HARBORSTONE_ORG_ID, auth_after.id)
        replay_rejected = {"rejected": False, "VIOLATION": "a consumed authorization was reused"}
    except ConflictError as exc:
        replay_rejected = {"rejected": True, "message": str(exc)}

    proof = aiproof_generator.generate_signed_aiproof(
        metadata=ProofMetadata(
            aiproof_id=f"proof-{d2.intent_id}",
            organization_id=HARBORSTONE_ORG_ID,
            governance_evaluation_id=d2.policy_resolution_id,
            correlation_id=d2_intent.correlation_id if d2_intent else None,
            governed_outcome=GovernedOutcome.APPROVED_AND_EXECUTED,
        ),
        actor_identity=ActorIdentityRef(actor_identity_id=HARBORSTONE_AIRA_ACTOR_ID),
        intent=IntentRef(
            intent_id=d2.intent_id,
            intent_type=d2_intent.intent_type if d2_intent else None,
            action=d2_intent.action if d2_intent else None,
            amount_minor=d2_intent.amount_minor if d2_intent else None,
            amount_currency=d2_intent.amount_currency if d2_intent else None,
        ),
        decision=DecisionRef(
            decision_id=d2.id,
            outcome=d2.outcome,
            reason_codes=json.loads(d2.reason_codes or "[]"),
            supersession_status=d2.supersession_status,
            prior_decision_id=d2.prior_decision_id,
            decision_hash=d2.decision_hash,
        ),
        execution_authorization=ExecutionAuthorizationRef(
            execution_authorization_id=auth_after.id,
            status=consumed_auth.status,
            authorized_action=auth_after.authorized_action,
            authorization_hash=auth_after.authorization_hash,
        ),
        external_execution_result=ExternalExecutionResultRef(
            external_execution_result_id=execution_result.id,
            adapter=execution_result.adapter,
            status=execution_result.status,
            external_reference=execution_result.external_reference,
            settlement_chain=execution_result.settlement_chain,
        ),
        timestamps=ProofTimestamps(
            generated_at=datetime.now(timezone.utc).isoformat(),
            decided_at=d2.decided_at.isoformat() if d2.decided_at else None,
            authorized_at=auth_after.authorized_at.isoformat() if auth_after.authorized_at else None,
            executed_at=execution_result.executed_at.isoformat() if execution_result.executed_at else None,
        ),
    )
    aiproof_row = aiproof_service.store_aiproof(db, proof)
    verification = verify_aiproof(proof)

    scenarios.append(
        {
            "id": "4f",
            "title": (
                "4c's APPROVED decision: authorization verify/consume, "
                "external execution result, canonical AIProof generate + verify"
            ),
            "proves": (
                "the second half of the governed-action chain -- APPROVED -> "
                "signed ExecutionAuthorization -> independent verify() (ISSUED "
                "-> ACTIVE) -> an external execution result recorded against it "
                "-> one-time consume() (ACTIVE -> CONSUMED, replay rejected) -> "
                "a canonical AIProof built from these exact real records, "
                "signed, and independently re-verified (hash + component "
                "hashes + signature all reproduce). Chains directly off the "
                "same APPROVED decision 4c got a real CompliIdentity "
                "authority-context response for."
            ),
            "does_NOT_prove": (
                "anything about CompliIdentity -- no further CompliIdentity "
                "calls happen after authorization is issued; this is entirely "
                "CompliAGL-internal from here on"
            ),
            "expected": {
                "verify_valid": True,
                "consume_ok": True,
                "replay_rejected": True,
                "aiproof_valid": True,
            },
            "source_decision_id": d2.id,
            "execution_authorization_id": auth_after.id,
            "verify_result": verify_result,
            "external_execution_result": {
                "id": execution_result.id,
                "status": execution_result.status,
                "adapter": execution_result.adapter,
                "external_reference": execution_result.external_reference,
            },
            "consumed_authorization_status": consumed_auth.status,
            "replay_attempt": replay_rejected,
            "aiproof": {
                "aiproof_id": aiproof_row.id,
                "aiproof_hash": proof.aiproof_hash,
                "governed_outcome": proof.metadata.governed_outcome.value,
                "component_hashes": dict(proof.component_hashes),
            },
            "aiproof_verification": verification.model_dump(),
            "PASS": (
                verify_result is not None
                and verify_result["valid"] is True
                and consumed_auth.status == "CONSUMED"
                and replay_rejected.get("rejected") is True
                and execution_result.status == "CONFIRMED"
                and verification.valid is True
            ),
        }
    )

    # --- 4e: aggregate check ------------------------------------------- #
    e_ok = all(
        s["no_execution_authorization"].get("issued") is False
        for s in scenarios
        if "no_execution_authorization" in s
    )
    scenarios.append(
        {
            "id": "4e",
            "title": "no ExecutionAuthorization is issued for any DENIED/ESCALATED decision",
            "proves": (
                "authorization_service.issue() raises ConflictError for every "
                "non-APPROVED decision above (see each scenario's "
                "no_execution_authorization block)"
            ),
            "does_NOT_prove": "n/a",
            "expected": {"all_issue_attempts_rejected": True},
            "PASS": e_ok,
        }
    )

    passed = sum(1 for s in scenarios if s.get("PASS"))
    out = {
        "_WARNING": (
            "Sanctions screening in this run uses the real "
            "harborstone-sentry-sanctions-screening connector against its "
            "own simulated dataset (claims.simulation=True), not a real "
            "OFAC/vendor lookup. Every scenario's resource_instance is a "
            "case id (not a wallet id), so screening always resolves NO_MATCH. "
            "These results prove the CompliIdentity authority-context "
            "integration, the decision-engine wiring, and (4f) the "
            "APPROVED -> authorization -> AIProof chain. They do NOT prove a "
            "real sanctions-list lookup."
        ),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "compliidentity_base_url": os.environ["COMPLIIDENTITY_BASE_URL"],
        "compliidentity_service_principal_id": os.environ[
            "COMPLIIDENTITY_SERVICE_PRINCIPAL_ID"
        ],
        "tenant__organization_id": HARBORSTONE_ORG_ID,
        "case_resource_instance": CASE,
        "actor_principal_ids": principals,
        "sanctions_screening": {
            "control_id": "CTL-HARBORSTONE-SANCTIONS-SCREENING",
            "connector_id": "harborstone-sentry-sanctions-screening",
            "is_mock": False,
            "simulated_lookup": True,
            "reference": (
                "backend/app/services/evidence/connectors/"
                "harborstone_sentry_screening.py"
            ),
        },
        "summary": {"passed": passed, "total": len(scenarios)},
        "scenarios": scenarios,
    }
    with open(_RESULTS_PATH, "w") as fh:
        json.dump(out, fh, indent=2, default=str)

    print(f"\n{'='*70}")
    for s in scenarios:
        mark = "PASS" if s.get("PASS") else "FAIL"
        extra = ""
        view = s.get("decision") or s.get("reevaluated_decision")
        if view is not None:
            extra = (
                f"  -> {view['outcome']}  "
                f"authority_reason={view['authority_reason']}  "
                f"codes={view['reason_codes']}"
            )
        elif "approval_attempt" in s:
            extra = f"  -> approval {s['approval_attempt'].get('reason', 'rejected')}"
        print(f"[{mark}] {s['id']:20} {s['title']}{extra}")
    print(f"{'='*70}\n{passed}/{len(scenarios)} scenarios passed")
    print(f"--- results written: {_RESULTS_PATH} ---")
    db.close()
    return 0 if passed == len(scenarios) else 1


if __name__ == "__main__":
    raise SystemExit(main())
