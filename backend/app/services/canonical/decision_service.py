"""Deterministic Decision service — the canonical Decision stage.

The Decision stage runs **after** Assessment and maps the *factual* assessment
(together with all upstream canonical inputs and the **explicit** decision
conditions from the governing governance package) into exactly one business
outcome: ``APPROVED``, ``DENIED`` or ``ESCALATED``.

Design guarantees
-----------------

* **Deterministic — never probabilistic.** Decision conditions are evaluated by
  the restricted, side-effect-free expression interpreter (no ``eval``/``exec``,
  no model calls). Identical inputs and package versions always produce the same
  decision hash.
* **Separate from Assessment.** Assessment stays factual (SATISFIED /
  NOT_SATISFIED / NOT_EVALUABLE / MANUAL_REVIEW_REQUIRED); this stage owns the
  business outcome.
* **Fail-closed.** ``APPROVED`` is only ever produced when an explicit decision
  condition allows it *and* the assessment is ``SATISFIED``. A
  ``NOT_EVALUABLE`` assessment can never silently become ``APPROVED``.
* **Immutable.** A decision is never mutated. Re-evaluation creates a **new**
  :class:`Decision` and supersedes the prior current decision.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.decision import Decision
from app.models.policy_resolution import PolicyResolution
from app.repositories.canonical import (
    ActorIdentityRepository,
    AssessmentRepository,
    CanonicalEvidencePackageRepository,
    DecisionRepository,
    EscalationApprovalRepository,
    ExecutableGovernancePackageRepository,
    IntentRepository,
    NormalizedEvidenceRepository,
    OperationalContextRepository,
    PolicyResolutionRepository,
    TargetRepository,
)
from app.services.canonical import assessment_service, runtime_facts
from app.services.canonical import authority_context_service
from app.services.canonical.authority_context_service import AuthorityContext
from app.services.canonical.deterministic_expression import (
    DETERMINISTIC_ENGINE_VERSION,
)
from app.services.canonical.errors import NotFoundError
from app.services.canonical.package_interpreter import (
    ExpressionError,
    evaluate_expression,
)
from app.utils.canonical_enums import (
    AssessmentOutcome,
    CanonicalActorType,
    DecisionOutcome,
    DecisionSupersessionStatus,
    EscalationApprovalStatus,
    PolicyResolutionStatus,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now


def _load(raw: Optional[str]) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return None


# --------------------------------------------------------------------------- #
# Deterministic decision-condition evaluation
# --------------------------------------------------------------------------- #
def _evaluate_conditions(
    conditions: list[dict[str, Any]], context: dict[str, Any]
) -> tuple[Optional[str], list[dict[str, Any]]]:
    """Evaluate explicit decision conditions in deterministic order.

    Returns ``(condition_outcome, triggered)`` where ``condition_outcome`` is the
    business outcome selected by the matched conditions (or ``None`` when no
    condition matched), and ``triggered`` is the ordered list of conditions whose
    expression evaluated to true.
    """
    ordered = sorted(
        (c for c in conditions if isinstance(c, dict)),
        key=lambda c: (
            c.get("priority", 100),
            str(c.get("package_id", "")),
            str(c.get("condition_id", "")),
        ),
    )

    outcome: Optional[str] = None
    triggered: list[dict[str, Any]] = []
    for condition in ordered:
        expression = condition.get("expression", "")
        try:
            matched = bool(evaluate_expression(expression, context))
        except ExpressionError:
            # A malformed condition is fail-closed: treated as non-matching but
            # never raised at runtime.
            matched = False
        if not matched:
            continue
        triggered.append(
            {
                "condition_id": condition.get("condition_id"),
                "package_id": condition.get("package_id"),
                "resulting_decision": condition.get("resulting_decision"),
                "reason_code": condition.get("reason_code"),
                "priority": condition.get("priority"),
                "terminal": bool(condition.get("terminal", True)),
            }
        )
        outcome = condition.get("resulting_decision") or outcome
        if condition.get("terminal", True):
            break
    return outcome, triggered


def _resolve_outcome(
    *,
    no_policy: bool,
    condition_outcome: Optional[str],
    assessment_outcome: str,
    authority_status: Optional[str] = None,
) -> tuple[str, list[str]]:
    """Map assessment + explicit decision conditions to a business outcome.

    The mapping is fail-closed:

    * a terminal ``DENIED`` condition (policy prohibition) always denies;
    * a ``MANUAL_REVIEW_REQUIRED`` / ``NOT_EVALUABLE`` assessment escalates and
      can never be approved;
    * a ``NOT_SATISFIED`` assessment (failed mandatory control) denies unless the
      policy explicitly escalates for remediation;
    * ``APPROVED`` requires both an explicit approving condition and a
      ``SATISFIED`` assessment -- and, when the governing package required a
      CompliIdentity authority-context check, that the check actually
      succeeded (``authority_status != "UNAVAILABLE"``). This mirrors the
      ``NOT_EVALUABLE`` guard above: when the authority plane's state is
      simply unknown (unreachable, timed out, malformed, or CompliIdentity's
      own ``context_unevaluable`` fail-closed response), that is never a
      business fact a package condition should have to remember to check --
      it structurally downgrades to ESCALATED regardless of which decision
      condition matched. Known-bad authority reasons (permission_missing,
      delegation_revoked, principal_not_found, ...) are real facts CompliIdentity
      did successfully report, so those stay purely package-authored via
      ``authority.reason`` conditions, same as any other runtime fact.
      ``authority_status`` is ``None`` whenever the package didn't declare
      ``requires_authority_context`` -- no guard applies, and this branch
      behaves exactly as it did before this integration existed.
    """
    D = DecisionOutcome
    A = AssessmentOutcome

    if no_policy:
        return D.DENIED.value, ["NO_APPLICABLE_POLICY"]

    # A terminal policy prohibition denies regardless of the assessment.
    if condition_outcome == D.DENIED.value:
        return D.DENIED.value, ["POLICY_PROHIBITION"]

    if assessment_outcome == A.MANUAL_REVIEW_REQUIRED.value:
        return D.ESCALATED.value, ["ASSESSMENT_MANUAL_REVIEW_REQUIRED"]

    if assessment_outcome == A.NOT_EVALUABLE.value:
        # NOT_EVALUABLE can never silently become APPROVED.
        return D.ESCALATED.value, ["ASSESSMENT_NOT_EVALUABLE"]

    if assessment_outcome == A.NOT_SATISFIED.value:
        if condition_outcome == D.ESCALATED.value:
            return D.ESCALATED.value, ["CONTROL_REMEDIATION_REQUIRED"]
        return D.DENIED.value, ["MANDATORY_CONTROL_FAILED"]

    # assessment SATISFIED
    if condition_outcome == D.APPROVED.value:
        if authority_status == "UNAVAILABLE":
            return D.ESCALATED.value, ["AUTHORITY_CONTEXT_UNAVAILABLE"]
        return D.APPROVED.value, ["APPROVED_BY_POLICY"]
    if condition_outcome == D.ESCALATED.value:
        return D.ESCALATED.value, ["ESCALATED_BY_POLICY"]
    # No explicit approving condition matched -> fail closed.
    return D.DENIED.value, ["NO_DECISION_CONDITION_MATCHED"]


# --------------------------------------------------------------------------- #
# Input gathering
# --------------------------------------------------------------------------- #
def _gather_inputs(db: Session, org: str, resolution: PolicyResolution):
    actor = ActorIdentityRepository(db).get(org, resolution.actor_identity_id)
    if actor is None:
        raise NotFoundError(
            f"ActorIdentity not found: {resolution.actor_identity_id}"
        )
    intent = IntentRepository(db).get(org, resolution.intent_id)
    if intent is None:
        raise NotFoundError(f"Intent not found: {resolution.intent_id}")
    target = (
        TargetRepository(db).get(org, resolution.target_id)
        if resolution.target_id
        else None
    )
    context = (
        OperationalContextRepository(db).get(org, resolution.operational_context_id)
        if resolution.operational_context_id
        else None
    )
    return actor, intent, target, context


def _package_conditions(
    db: Session, org: str, selected_packages: list[dict[str, Any]]
) -> tuple[
    list[dict[str, Any]], list[dict[str, Any]], list[str], Optional[str], bool
]:
    """Return (decision_conditions, package_refs, requirement_ids, package_hash,
    requires_authority_context).

    ``requires_authority_context`` is True when *any* selected package
    declares it -- a CompliIdentity call is made if any applicable package
    needs one, even if others don't.
    """
    conditions: list[dict[str, Any]] = []
    package_refs: list[dict[str, Any]] = []
    requirement_ids: set[str] = set()
    requires_authority_context = False

    repo = ExecutableGovernancePackageRepository(db)
    for entry in selected_packages:
        if not isinstance(entry, dict):
            continue
        package_id = entry.get("package_id")
        for req in entry.get("requirements") or []:
            if isinstance(req, dict) and req.get("requirement_id"):
                requirement_ids.add(str(req["requirement_id"]))
        pkg = repo.get(org, package_id) if package_id else None
        package_refs.append(
            {
                "package_id": package_id,
                "package_name": entry.get("package_name"),
                "package_version": entry.get("package_version"),
                "package_hash": (
                    pkg.package_hash if pkg is not None else entry.get("package_hash")
                ),
            }
        )
        if pkg is None:
            continue
        if getattr(pkg, "requires_authority_context", False):
            requires_authority_context = True
        for cond in _load(pkg.decision_conditions) or []:
            if isinstance(cond, dict):
                conditions.append({**cond, "package_id": package_id})

    package_refs.sort(key=lambda p: str(p.get("package_id") or ""))
    aggregate_hash = hash_dict({"packages": package_refs}) if package_refs else None
    return (
        conditions,
        package_refs,
        sorted(requirement_ids),
        aggregate_hash,
        requires_authority_context,
    )


# --------------------------------------------------------------------------- #
# CompliIdentity authority-context integration
# --------------------------------------------------------------------------- #
def _authority_principal_id(actor) -> Optional[str]:
    """Map an ActorIdentity to the ``principal_id`` CompliIdentity's
    authority-context endpoint expects.

    ASSUMPTION, confirmed not contractually specified by CompliIdentity's
    contract doc (``principal_id`` is documented as an opaque, tenant-scoped
    identifier from CompliIdentity's point of view -- the mapping is a
    CompliAGL-side integration choice): human actors use
    ``human_principal_id``; every other actor type (agent, service, etc.)
    uses ``wallet_or_agent_account_id``. If this turns out wrong against
    real CompliIdentity, it's a one-line fix here.
    """
    if actor.actor_type == CanonicalActorType.HUMAN.value:
        return actor.human_principal_id
    return actor.wallet_or_agent_account_id or actor.human_principal_id


def _authority_request_params(intent) -> dict[str, Any]:
    """Map an Intent to CompliIdentity's ``resource`` / ``action`` /
    ``resource_instance`` probe fields.

    All three come from ``intent.parameters`` when the governance package
    author supplied them, following the existing ``compliidentity_resource``
    pattern:

    * ``compliidentity_resource`` -> ``resource`` (falls back to
      ``intent.intent_type``).
    * ``compliidentity_action`` -> ``action`` (falls back to ``"request"``).
      CompliIdentity's real permission model keys on the semantic verb --
      ``read`` / ``propose`` / ``approve`` -- not a generic probe verb;
      confirmed against the demo3 acceptance run, where every acceptance
      check used the real action. The ``"request"`` fallback keeps every
      package that predates this (and every non-opt-in package) unchanged.
    * ``compliidentity_resource_instance`` -> ``resource_instance``, sent
      only when supplied. This is what makes CompliIdentity's resource-scope
      narrowing meaningful -- e.g. a grant scoped to one case, inherited by a
      delegate: without the instance the probe can't see the scope bound.

    When the intent carries an amount it's passed as the ``attribute`` /
    ``value`` pair so CompliIdentity's ``authority_for_request`` is scoped to
    the actual proposed action (and its ``approval_required`` /
    ``limit_exceeded`` reflect the real threshold), not just a liveness check.
    """
    params = _load(intent.parameters) or {}
    resource = params.get("compliidentity_resource") or intent.intent_type
    action = params.get("compliidentity_action") or "request"
    result: dict[str, Any] = {"resource": resource, "action": action}
    resource_instance = params.get("compliidentity_resource_instance")
    if resource_instance is not None:
        result["resource_instance"] = resource_instance
    if intent.amount_minor is not None:
        result["attribute"] = "amount"
        result["value"] = str(intent.amount_minor)
    return result


def _fetch_authority_context(org: str, actor, intent) -> AuthorityContext:
    """Fetch authority context for this decision. Never raises -- a missing
    client, missing principal mapping, or any client-reported failure all
    normalize to ``UNAVAILABLE`` via the same path as a network error.
    """
    client = authority_context_service.default_client()
    if client is None:
        return AuthorityContext(status="UNAVAILABLE", reason="not_configured")
    principal_id = _authority_principal_id(actor)
    if not principal_id:
        return AuthorityContext(status="UNAVAILABLE", reason="no_principal_id")
    return client.fetch(
        organization_id=org,
        principal_id=principal_id,
        **_authority_request_params(intent),
    )


def _required_approver_types(
    authority: Optional[AuthorityContext], action: str
) -> list[str]:
    """The approver principal type(s) CompliIdentity declared were required to
    approve ``action``, from the authority context's ``applicable_approvals``.

    Empty when there is no authority context or CompliIdentity named no
    approval requirement for this action (e.g. the escalation was driven by a
    package's own amount threshold rather than ``authority.approval_required``).
    """
    if authority is None:
        return []
    types = {
        str(entry["approver_principal_type"])
        for entry in authority.applicable_approvals
        if isinstance(entry, dict)
        and entry.get("action") == action
        and entry.get("approver_principal_type")
    }
    return sorted(types)


def _evidence_claims_facts(
    db: Session, org: str, evidence_pkg
) -> dict[str, dict[str, Any]]:
    """The normalized (validated) evidence claims, keyed by evidence
    requirement id, for the decision context.

    This is the same fact vocabulary ``control_evaluation_service`` already
    exposes to control expressions -- surfaced here so a package's *decision*
    conditions can key off a concrete evidence signal (e.g. a sanctions
    screening ``result``) rather than only the coarse assessment verdict.

    Only the first normalized item per requirement is exposed (requirements
    used this way are single-cardinality); an absent requirement is simply an
    absent key, so a condition that references it fails closed.
    """
    claims_by_req: dict[str, dict[str, Any]] = {}
    if evidence_pkg is None or not getattr(
        evidence_pkg, "collection_job_id", None
    ):
        return claims_by_req
    normalized = NormalizedEvidenceRepository(db).list_for_job(
        org, evidence_pkg.collection_job_id
    )
    for norm in normalized:
        req_id = norm.evidence_requirement_id
        if req_id in claims_by_req:
            continue
        claims = _load(norm.normalized_claims)
        claims_by_req[req_id] = claims if isinstance(claims, dict) else {}
    return claims_by_req


def _build_context(
    actor,
    intent,
    target,
    context,
    assessment,
    evidence_pkg,
    authority=None,
    approval_facts=None,
    evidence_claims=None,
):
    facts = runtime_facts.build_facts(
        actor=actor,
        intent=intent,
        target=target,
        context=context,
        authority=authority,
        approval_facts=approval_facts,
    )
    intent_params = facts.get("intent", {}).get("parameters", {}) or {}
    decision_context: dict[str, Any] = dict(facts)
    # Expose intent parameters as bare names for convenience in expressions.
    for key, value in intent_params.items():
        decision_context.setdefault(key, value)
    decision_context["assessment"] = {
        "overall_result": assessment.overall_result,
        "evidence_sufficiency_result": assessment.evidence_sufficiency_result,
        "mandatory_control_summary": _load(assessment.mandatory_control_summary)
        or {},
    }
    decision_context["evidence"] = {
        "package_id": evidence_pkg.id if evidence_pkg is not None else None,
        "package_hash": evidence_pkg.package_hash
        if evidence_pkg is not None
        else None,
    }
    # Normalized evidence claims by requirement id. Bound into the decision's
    # identity already via ``evidence_package_hash`` in input_hash -- exposed
    # here only so decision conditions can read the content.
    decision_context["evidence_claims"] = dict(evidence_claims or {})
    return facts, decision_context


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def decide_for_resolution(
    db: Session,
    organization_id: str,
    policy_resolution_id: str,
    *,
    prior_decision_id: Optional[str] = None,
) -> Decision:
    """Produce a deterministic :class:`Decision` for a resolved evaluation.

    A previously-current decision for the same evaluation is automatically
    superseded (re-evaluation creates a new immutable decision).
    """
    org = organization_id

    resolution = PolicyResolutionRepository(db).get(org, policy_resolution_id)
    if resolution is None:
        raise NotFoundError(
            f"PolicyResolution not found: {policy_resolution_id}"
        )

    actor, intent, target, context = _gather_inputs(db, org, resolution)

    # Assessment (factual). Always recompute: assess_for_resolution's own
    # upstream dependencies (evidence sufficiency, control determination) are
    # now dedup-on-input-hash, so this is cheap when nothing has changed and
    # correctly reflects newly-completed evidence when something has. Reusing
    # `assessment_service.latest_for_resolution` here unconditionally would
    # permanently pin a policy_resolution_id to whatever assessment happened
    # to be computed on the very first decide() call, no matter how the
    # upstream evidence/control state improves afterward.
    assessment = assessment_service.assess_for_resolution(
        db, org, policy_resolution_id
    )

    evidence_pkg = CanonicalEvidencePackageRepository(db).latest_for_evaluation(
        org, policy_resolution_id
    )

    # Use exactly the control evaluations this assessment aggregated, not a
    # standing query over every ControlEvaluation row ever created for this
    # resolution -- assess_for_resolution creates a fresh batch on every
    # call (never dedups), so querying "all history" here would make the
    # list -- and therefore input_hash -- grow with duplicate business-ids
    # on every decide() call even when nothing upstream actually changed.
    control_evaluation_ids = sorted(_load(assessment.control_evaluation_ids) or [])

    selected_packages = _load(resolution.selected_packages) or []
    (
        conditions,
        package_refs,
        requirement_ids,
        policy_package_hash,
        requires_authority_context,
    ) = _package_conditions(db, org, selected_packages)

    no_policy = (
        not selected_packages
        or resolution.status == PolicyResolutionStatus.NO_APPLICABLE_POLICY.value
    )

    # Only ever call CompliIdentity for packages that opted in
    # (requires_authority_context=True) and only when there's an applicable
    # policy to begin with -- a no_policy resolution already resolves to
    # DENIED regardless, so the call would be pure waste.
    authority: Optional[AuthorityContext] = None
    if requires_authority_context and not no_policy:
        authority = _fetch_authority_context(org, actor, intent)

    # A re-decision (prior_decision_id set) picks up a current escalation
    # approval for that prior decision as the ``approval`` runtime fact -- a
    # package condition upgrades the escalation off it; the engine's
    # _resolve_outcome is unchanged. Only ACTIVE approvals are returned;
    # whether the window has passed is exposed as ``approval.expired``.
    decided_at = utc_now()
    approval_obj = None
    approval_facts = None
    if prior_decision_id is not None:
        approval_obj = EscalationApprovalRepository(db).current_for_decision(
            org, prior_decision_id
        )
        if approval_obj is not None:
            approval_facts = runtime_facts.build_approval_facts(
                approval_obj, now=decided_at
            )

    evidence_claims = _evidence_claims_facts(db, org, evidence_pkg)

    facts, decision_context = _build_context(
        actor,
        intent,
        target,
        context,
        assessment,
        evidence_pkg,
        authority,
        approval_facts,
        evidence_claims,
    )

    condition_outcome, triggered = (
        (None, []) if no_policy else _evaluate_conditions(conditions, decision_context)
    )

    outcome, mapping_reasons = _resolve_outcome(
        no_policy=no_policy,
        condition_outcome=condition_outcome,
        assessment_outcome=assessment.overall_result,
        authority_status=authority.status if authority is not None else None,
    )

    reason_codes = [f"DECISION_{outcome}"] + mapping_reasons
    for cond in triggered:
        code = cond.get("reason_code")
        if code and code not in reason_codes:
            reason_codes.append(code)

    # --- Deterministic hashes over the bound inputs ---
    actor_hash = hash_dict(facts.get("actor") or {})
    intent_hash = hash_dict(facts.get("intent") or {})
    target_hash = hash_dict(facts["target"]) if "target" in facts else None
    context_hash = hash_dict(facts["context"]) if "context" in facts else None
    evidence_package_hash = (
        evidence_pkg.package_hash if evidence_pkg is not None else None
    )
    # Content-hashes the normalized authority facts, including
    # CompliIdentity's own authority_revision fingerprint -- see the
    # authority_hash column comment on the Decision model for why this binds
    # the snapshot's identity rather than duplicating it as a second audit
    # record. None when the package didn't require an authority-context call.
    authority_hash = hash_dict(facts["authority"]) if "authority" in facts else None
    # Content hash of the ``approval`` fact -- bound into input_hash exactly
    # like authority_hash. None on a first decision (no prior_decision_id) or a
    # re-decision that found no current approval. ``required_approver_types``
    # is persisted (not hashed separately) -- it is already covered by
    # authority_hash via authority.applicable_approvals.
    approval_hash = hash_dict(facts["approval"]) if "approval" in facts else None
    probe_action = _authority_request_params(intent).get("action")
    required_approver_types = _required_approver_types(authority, probe_action)

    # NOTE for a future cross-repo hash-mismatch debug -- input_hash shape has
    # changed three times, all the same class of change (see
    # CROSS_REPO_ASK_compliledger_input_hash_verification.md):
    #   1. migration 0014 added the "authority_hash" key (null for packages
    #      that don't opt into the CompliIdentity check).
    #   2. this commit (migration 0017) adds the "approval_hash" key (null on
    #      every decision that isn't a re-decision consuming an approval).
    #   3. this commit also changes what "authority_hash" *hashes over*:
    #      runtime_facts.build_authority_facts now includes
    #      authority.applicable_approvals, so authority_hash differs for
    #      authority-gated decisions from here on even at identical inputs.
    # Checked at each point: no in-repo code recomputes input_hash from a
    # persisted Decision, and IntegrationEventType.DECISION_CREATED has no live
    # publisher. Not ruled out: an external system (CompliLedger) polling the
    # public DecisionResponse.input_hash and recomputing it itself.
    input_hash = hash_dict(
        {
            "engine_version": DETERMINISTIC_ENGINE_VERSION,
            "organization_id": org,
            "policy_resolution_id": policy_resolution_id,
            # assessment_hash (a deterministic content hash) is the input
            # identity here, not assessment.id -- assess_for_resolution
            # creates a fresh row on every call by design (like Decision
            # itself), so a random per-row id must never leak into a
            # "deterministic inputs" hash.
            "assessment_hash": assessment.assessment_hash,
            "assessment_result": assessment.overall_result,
            "applicable_package_ids": package_refs,
            "applicable_requirement_ids": requirement_ids,
            "control_evaluation_ids": control_evaluation_ids,
            "evidence_package_id": evidence_pkg.id if evidence_pkg else None,
            "evidence_package_hash": evidence_package_hash,
            "actor_hash": actor_hash,
            "intent_hash": intent_hash,
            "target_hash": target_hash,
            "context_hash": context_hash,
            "authority_hash": authority_hash,
            "approval_hash": approval_hash,
        }
    )
    decision_hash = hash_dict(
        {
            "input_hash": input_hash,
            "outcome": outcome,
            "reason_codes": reason_codes,
            "decision_conditions_triggered": triggered,
            "prior_decision_id": prior_decision_id,
        }
    )

    obj = Decision(
        organization_id=org,
        governance_evaluation_id=policy_resolution_id,
        intent_id=intent.id,
        evaluation_id=policy_resolution_id,
        policy_resolution_id=policy_resolution_id,
        assessment_id=assessment.id,
        outcome=outcome,
        reason_codes=json.dumps(reason_codes),
        policy_version=(
            package_refs[0].get("package_version") if package_refs else None
        ),
        decision_conditions_triggered=json.dumps(triggered),
        applicable_package_ids=json.dumps(package_refs),
        applicable_requirement_ids=json.dumps(requirement_ids),
        control_evaluation_ids=json.dumps(control_evaluation_ids),
        evidence_package_id=evidence_pkg.id if evidence_pkg is not None else None,
        evidence_package_hash=evidence_package_hash,
        assessment_hash=assessment.assessment_hash,
        policy_package_hash=policy_package_hash,
        actor_hash=actor_hash,
        intent_hash=intent_hash,
        target_hash=target_hash,
        context_hash=context_hash,
        authority_status=authority.status if authority is not None else None,
        authority_reason=authority.reason if authority is not None else None,
        authority_hash=authority_hash,
        required_approver_types=(
            json.dumps(required_approver_types)
            if required_approver_types
            else None
        ),
        approval_hash=approval_hash,
        engine_version=DETERMINISTIC_ENGINE_VERSION,
        input_hash=input_hash,
        decision_hash=decision_hash,
        decided_at=decided_at,
        expires_at=intent.expires_at,
        prior_decision_id=prior_decision_id,
        supersession_status=DecisionSupersessionStatus.CURRENT.value,
    )

    repo = DecisionRepository(db)

    # Supersede any current prior decision for this evaluation (immutability:
    # the prior decision is never mutated except to record it was superseded).
    prior = None
    if prior_decision_id is not None:
        prior = repo.get(org, prior_decision_id)
    if prior is None:
        prior = repo.current_for_evaluation(org, policy_resolution_id)
    obj = repo.add(obj)
    if prior is not None and prior.id != obj.id:
        prior.supersession_status = DecisionSupersessionStatus.SUPERSEDED.value
        prior.superseded_by_decision_id = obj.id
        if obj.prior_decision_id is None:
            obj.prior_decision_id = prior.id
        repo.save(prior)
        repo.save(obj)

    # A current approval that actually drove an APPROVED re-decision is spent:
    # one approval authorises exactly one re-decision. An unexpired approval
    # that did NOT upgrade the escalation (e.g. the package condition still
    # escalated for another reason) is left ACTIVE; an expired one is left for
    # a later sweep to mark EXPIRED.
    if (
        approval_obj is not None
        and outcome == DecisionOutcome.APPROVED.value
        and approval_facts is not None
        and not approval_facts.get("expired")
    ):
        approval_obj.status = EscalationApprovalStatus.CONSUMED.value
        approval_obj.consumed_by_decision_id = obj.id
        EscalationApprovalRepository(db).save(approval_obj)
    return obj


def get(
    db: Session, organization_id: str, resource_id: str
) -> Optional[Decision]:
    return DecisionRepository(db).get(organization_id, resource_id)


def list_(
    db: Session, organization_id: str, *, skip: int = 0, limit: int = 100
) -> Sequence[Decision]:
    return DecisionRepository(db).list(organization_id, skip=skip, limit=limit)


def explain(
    db: Session, organization_id: str, resource_id: str
) -> Optional[dict[str, Any]]:
    """Return a structured, human-auditable explanation of a decision."""
    decision = DecisionRepository(db).get(organization_id, resource_id)
    if decision is None:
        return None
    return {
        "decision_id": decision.id,
        "result": decision.outcome,
        "reason_codes": _load(decision.reason_codes) or [],
        "decision_conditions_triggered": _load(
            decision.decision_conditions_triggered
        )
        or [],
        "evaluation_id": decision.evaluation_id,
        "policy_resolution_id": decision.policy_resolution_id,
        "assessment_id": decision.assessment_id,
        "assessment_hash": decision.assessment_hash,
        "applicable_package_ids": _load(decision.applicable_package_ids) or [],
        "applicable_requirement_ids": _load(decision.applicable_requirement_ids)
        or [],
        "control_evaluation_ids": _load(decision.control_evaluation_ids) or [],
        "evidence_package_id": decision.evidence_package_id,
        "evidence_package_hash": decision.evidence_package_hash,
        "policy_package_hash": decision.policy_package_hash,
        "authority_status": decision.authority_status,
        "authority_reason": decision.authority_reason,
        "required_approver_types": _load(decision.required_approver_types) or [],
        "input_hashes": {
            "actor_hash": decision.actor_hash,
            "intent_hash": decision.intent_hash,
            "target_hash": decision.target_hash,
            "context_hash": decision.context_hash,
            "authority_hash": decision.authority_hash,
            "approval_hash": decision.approval_hash,
        },
        "engine_version": decision.engine_version,
        "decision_hash": decision.decision_hash,
        "decided_at": decision.decided_at,
        "expires_at": decision.expires_at,
        "prior_decision_id": decision.prior_decision_id,
        "superseded_by_decision_id": decision.superseded_by_decision_id,
        "supersession_status": decision.supersession_status,
    }
