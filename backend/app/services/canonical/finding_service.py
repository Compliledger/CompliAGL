"""Finding service — generates and manages governance findings.

Findings are produced on the finding-and-remediation branch, which applies when
an assessment or decision is ``NOT_SATISFIED``, ``NOT_EVALUABLE``,
``MANUAL_REVIEW_REQUIRED``, ``DENIED`` or ``ESCALATED`` — subject to
governance-package configuration. Findings are generated from **explicit
governance rules** over the deterministic pipeline outputs (decision,
assessment, control evaluations and evidence sufficiency), never heuristically.

Not every denial is remediable: a terminal policy prohibition yields a finding
that is ``INELIGIBLE`` for remediation and terminal.
"""

from __future__ import annotations

import json
from typing import Any, Optional, Sequence

from sqlalchemy.orm import Session

from app.models.decision import Decision
from app.models.finding import Finding
from app.repositories.canonical import (
    AssessmentRepository,
    ControlEvaluationRepository,
    DecisionRepository,
    EvidenceSufficiencyRepository,
    ExecutableGovernancePackageRepository,
    FindingRepository,
    PolicyResolutionRepository,
)
from app.services.canonical.errors import NotFoundError
from app.utils.canonical_enums import (
    AssessmentOutcome,
    ControlEvaluationOutcome,
    DecisionOutcome,
    EvidenceRequirementSufficiency,
    FindingDecisionImpact,
    FindingStatus,
    FindingType,
    GovernanceSeverity,
    RemediationEligibility,
)
from app.utils.hashing import hash_dict
from app.utils.timestamps import utc_now


def _load(raw: Optional[str], default: Any = None) -> Any:
    if not raw:
        return default
    try:
        return json.loads(raw)
    except (ValueError, TypeError):
        return default


# --------------------------------------------------------------------------- #
# Governance-package remediation configuration
# --------------------------------------------------------------------------- #
_DEFAULT_TERMINAL_TYPES = frozenset({FindingType.POLICY_PROHIBITION.value})

# Finding types that are NEVER eligible for remediation, regardless of a
# package's ``remediation`` config. ``ESCALATION_APPROVAL_REQUIRED`` is resolved
# only by an authority-verified human approval + an explicit re-decision, so it
# must never acquire a remediation plan (which would route it into
# resolution_validation_service / reassessment_service — the rubber-stamp path
# this type exists to keep it out of).
_ALWAYS_INELIGIBLE = frozenset({FindingType.ESCALATION_APPROVAL_REQUIRED.value})


def _remediation_config(db: Session, org: str, decision: Decision) -> dict[str, Any]:
    """Aggregate the remediation configuration from the governing packages.

    Reads an optional ``remediation`` block from each package's
    ``package_metadata``:

    ``{"terminal_finding_types": [...], "ineligible_finding_types": [...]}``
    """
    terminal: set[str] = set(_DEFAULT_TERMINAL_TYPES)
    ineligible: set[str] = set(_DEFAULT_TERMINAL_TYPES)

    repo = ExecutableGovernancePackageRepository(db)
    package_refs = _load(decision.applicable_package_ids, []) or []
    for ref in package_refs:
        package_id = ref.get("package_id") if isinstance(ref, dict) else None
        if not package_id:
            continue
        pkg = repo.get(org, package_id)
        if pkg is None:
            continue
        metadata = _load(pkg.package_metadata, {}) or {}
        remediation = metadata.get("remediation") or {}
        for t in remediation.get("terminal_finding_types") or []:
            terminal.add(str(t))
        for t in remediation.get("ineligible_finding_types") or []:
            ineligible.add(str(t))
    return {"terminal_finding_types": terminal, "ineligible_finding_types": ineligible}


def _eligibility(
    finding_type: str, terminal: bool, config: dict[str, Any]
) -> str:
    if (
        terminal
        or finding_type in _ALWAYS_INELIGIBLE
        or finding_type in config["ineligible_finding_types"]
    ):
        return RemediationEligibility.INELIGIBLE.value
    return RemediationEligibility.ELIGIBLE.value


# --------------------------------------------------------------------------- #
# Finding construction
# --------------------------------------------------------------------------- #
def _severity_for(raw: Optional[str], default: str) -> str:
    if raw in {s.value for s in GovernanceSeverity}:
        return raw  # type: ignore[return-value]
    return default


def _decision_impact(decision: Decision, assessment_result: Optional[str]) -> str:
    if decision.outcome == DecisionOutcome.DENIED.value:
        return FindingDecisionImpact.DENIED.value
    if decision.outcome == DecisionOutcome.ESCALATED.value:
        if assessment_result == AssessmentOutcome.MANUAL_REVIEW_REQUIRED.value:
            return FindingDecisionImpact.MANUAL_REVIEW_REQUIRED.value
        if assessment_result == AssessmentOutcome.NOT_EVALUABLE.value:
            return FindingDecisionImpact.NOT_EVALUABLE.value
        return FindingDecisionImpact.ESCALATED.value
    return FindingDecisionImpact.ADVISORY.value


def _build_finding(
    *,
    org: str,
    decision: Decision,
    assessment,
    finding_type: str,
    title: str,
    description: str,
    severity: str,
    requirement_ids: Sequence[str],
    control_ids: Sequence[str],
    evidence_gap_ids: Sequence[str],
    reason_codes: Sequence[str],
    config: dict[str, Any],
) -> Finding:
    terminal = finding_type in config["terminal_finding_types"]
    eligibility = _eligibility(finding_type, terminal, config)
    assessment_result = assessment.overall_result if assessment else None
    decision_impact = _decision_impact(decision, assessment_result)

    identity = {
        "organization_id": org,
        "decision_id": decision.id,
        "finding_type": finding_type,
        "requirement_ids": sorted(requirement_ids),
        "control_ids": sorted(control_ids),
        "evidence_gap_ids": sorted(evidence_gap_ids),
    }
    finding_id = "FND-" + hash_dict(identity)[:16]
    finding_hash = hash_dict(
        {
            **identity,
            "severity": severity,
            "terminal": terminal,
            "remediation_eligibility": eligibility,
            "decision_impact": decision_impact,
            "reason_codes": sorted(reason_codes),
        }
    )
    return Finding(
        organization_id=org,
        finding_id=finding_id,
        evaluation_id=decision.evaluation_id or decision.policy_resolution_id,
        assessment_id=decision.assessment_id or (assessment.id if assessment else None),
        decision_id=decision.id,
        intent_id=decision.intent_id,
        actor_id=None,
        target_id=None,
        requirement_ids=json.dumps(sorted(requirement_ids)),
        control_ids=json.dumps(sorted(control_ids)),
        evidence_gap_ids=json.dumps(sorted(evidence_gap_ids)),
        title=title,
        description=description,
        severity=severity,
        finding_type=finding_type,
        decision_impact=decision_impact,
        remediation_eligibility=eligibility,
        terminal=terminal,
        status=FindingStatus.OPEN.value,
        reason_codes=json.dumps(sorted(reason_codes)),
        finding_hash=finding_hash,
    )


def _policy_prohibition(decision: Decision) -> Optional[dict[str, Any]]:
    """Return prohibition detail if the decision was a terminal denial."""
    reasons = _load(decision.reason_codes, []) or []
    triggered = _load(decision.decision_conditions_triggered, []) or []
    prohibition = any(
        isinstance(c, dict)
        and c.get("terminal", True)
        and c.get("resulting_decision") == DecisionOutcome.DENIED.value
        for c in triggered
    )
    if "POLICY_PROHIBITION" in reasons or prohibition:
        return {"reason_codes": [str(r) for r in reasons]}
    return None


def _escalation_approval_required(decision: Decision) -> Optional[dict[str, Any]]:
    """Detail if this decision escalated purely via a governance policy condition.

    ``ESCALATED_BY_POLICY`` is emitted only by
    ``decision_service._resolve_outcome`` and only for a ``SATISFIED``
    assessment whose decision conditions selected ``ESCALATED`` — i.e. no
    failing control, no manual-review assessment, no evidence gap. A package
    cannot forge that mapping code (its condition ``reason_code`` is appended
    separately). Such an escalation is resolvable only by an authority-verified
    human approval, so it gets a dedicated finding type.
    """
    if decision.outcome != DecisionOutcome.ESCALATED.value:
        return None
    reasons = _load(decision.reason_codes, []) or []
    if "ESCALATED_BY_POLICY" not in reasons:
        return None
    triggered = _load(decision.decision_conditions_triggered, []) or []
    escalating = [
        c
        for c in triggered
        if isinstance(c, dict)
        and c.get("resulting_decision") == DecisionOutcome.ESCALATED.value
    ]
    return {
        "reason_codes": [str(r) for r in reasons],
        "condition_reason_codes": [
            str(c["reason_code"]) for c in escalating if c.get("reason_code")
        ],
    }


# --------------------------------------------------------------------------- #
# Generation
# --------------------------------------------------------------------------- #
_BRANCH_ASSESSMENT_RESULTS = {
    AssessmentOutcome.NOT_SATISFIED.value,
    AssessmentOutcome.NOT_EVALUABLE.value,
    AssessmentOutcome.MANUAL_REVIEW_REQUIRED.value,
}
_BRANCH_DECISION_OUTCOMES = {
    DecisionOutcome.DENIED.value,
    DecisionOutcome.ESCALATED.value,
}


def branch_applies(decision: Decision, assessment) -> bool:
    """Whether the finding-and-remediation branch applies to this decision."""
    if decision.outcome in _BRANCH_DECISION_OUTCOMES:
        return True
    if assessment is not None and assessment.overall_result in _BRANCH_ASSESSMENT_RESULTS:
        return True
    return False


def generate_for_decision(
    db: Session, organization_id: str, decision_id: str
) -> list[Finding]:
    """Generate findings for a decision according to explicit governance rules.

    Idempotent: if findings already exist for the decision they are returned
    unchanged (findings are immutable statements of what was wrong).
    """
    org = organization_id
    decision = DecisionRepository(db).get(org, decision_id)
    if decision is None:
        raise NotFoundError(f"Decision not found: {decision_id}")

    repo = FindingRepository(db)
    existing = list(repo.list_for_decision(org, decision_id))
    if existing:
        return existing

    resolution_id = decision.policy_resolution_id or decision.evaluation_id
    assessment = None
    if decision.assessment_id:
        assessment = AssessmentRepository(db).get(org, decision.assessment_id)
    if assessment is None and resolution_id:
        assessment = AssessmentRepository(db).latest_for_resolution(org, resolution_id)

    if not branch_applies(decision, assessment):
        return []

    config = _remediation_config(db, org, decision)
    findings: list[Finding] = []

    # --- Rule 1: terminal policy prohibition (non-remediable) --------------- #
    prohibition = _policy_prohibition(decision)
    if prohibition is not None:
        findings.append(
            _build_finding(
                org=org,
                decision=decision,
                assessment=assessment,
                finding_type=FindingType.POLICY_PROHIBITION.value,
                title="Policy prohibition",
                description=(
                    "A terminal governance prohibition denied this intent. The "
                    "prohibition is not remediable."
                ),
                severity=GovernanceSeverity.CRITICAL.value,
                requirement_ids=[],
                control_ids=[],
                evidence_gap_ids=[],
                reason_codes=["FINDING_POLICY_PROHIBITION", *prohibition["reason_codes"]],
                config=config,
            )
        )

    # --- Rule 2: per failing control -------------------------------------- #
    control_evaluations = (
        ControlEvaluationRepository(db).list_for_resolution(org, resolution_id)
        if resolution_id
        else []
    )
    C = ControlEvaluationOutcome
    for ce in sorted(control_evaluations, key=lambda c: c.control_evaluation_id):
        req_ids = _load(ce.requirement_ids, []) or []
        ev_req_ids = _load(ce.evidence_requirement_ids, []) or []
        ce_reasons = _load(ce.reason_codes, []) or []
        if ce.result == C.NOT_SATISFIED.value:
            findings.append(
                _build_finding(
                    org=org,
                    decision=decision,
                    assessment=assessment,
                    finding_type=FindingType.CONTROL_FAILURE.value,
                    title=f"Control failure: {ce.control_id}",
                    description=(
                        f"Control {ce.control_id} was not satisfied by the "
                        "validated evidence."
                    ),
                    severity=_severity_for(ce.severity, GovernanceSeverity.HIGH.value),
                    requirement_ids=req_ids,
                    control_ids=[ce.control_id],
                    evidence_gap_ids=ev_req_ids,
                    reason_codes=["FINDING_CONTROL_FAILURE", *map(str, ce_reasons)],
                    config=config,
                )
            )
        elif ce.result == C.MANUAL_REVIEW_REQUIRED.value:
            findings.append(
                _build_finding(
                    org=org,
                    decision=decision,
                    assessment=assessment,
                    finding_type=FindingType.MANUAL_REVIEW.value,
                    title=f"Manual review required: {ce.control_id}",
                    description=(
                        f"Control {ce.control_id} requires human review before a "
                        "decision can be reached."
                    ),
                    severity=_severity_for(ce.severity, GovernanceSeverity.MEDIUM.value),
                    requirement_ids=req_ids,
                    control_ids=[ce.control_id],
                    evidence_gap_ids=ev_req_ids,
                    reason_codes=["FINDING_MANUAL_REVIEW", *map(str, ce_reasons)],
                    config=config,
                )
            )
        elif ce.result == C.NOT_EVALUABLE.value:
            authority = any(
                "AUTHORITY" in str(r).upper() or "DELEGATION" in str(r).upper()
                for r in ce_reasons
            )
            ftype = (
                FindingType.AUTHORITY_FAILURE.value
                if authority
                else FindingType.EVIDENCE_GAP.value
            )
            findings.append(
                _build_finding(
                    org=org,
                    decision=decision,
                    assessment=assessment,
                    finding_type=ftype,
                    title=f"Control not evaluable: {ce.control_id}",
                    description=(
                        f"Control {ce.control_id} could not be evaluated (missing "
                        "or indeterminate basis)."
                    ),
                    severity=_severity_for(ce.severity, GovernanceSeverity.HIGH.value),
                    requirement_ids=req_ids,
                    control_ids=[ce.control_id],
                    evidence_gap_ids=ev_req_ids,
                    reason_codes=["FINDING_NOT_EVALUABLE", *map(str, ce_reasons)],
                    config=config,
                )
            )

    # --- Rule 3: evidence-sufficiency gaps -------------------------------- #
    sufficiency = (
        EvidenceSufficiencyRepository(db).latest_for_resolution(org, resolution_id)
        if resolution_id
        else None
    )
    if sufficiency is not None:
        S = EvidenceRequirementSufficiency
        gap_states = {S.MISSING.value, S.PARTIAL.value}
        invalid_states = {S.INVALID.value, S.STALE.value}
        for entry in _load(sufficiency.requirement_results, []) or []:
            if not isinstance(entry, dict):
                continue
            state = entry.get("status") or entry.get("state")
            ev_req_id = entry.get("evidence_requirement_id")
            if state in gap_states:
                ftype = FindingType.EVIDENCE_GAP.value
                code = "FINDING_EVIDENCE_GAP"
            elif state in invalid_states:
                ftype = FindingType.INVALID_EVIDENCE.value
                code = "FINDING_INVALID_EVIDENCE"
            else:
                continue
            findings.append(
                _build_finding(
                    org=org,
                    decision=decision,
                    assessment=assessment,
                    finding_type=ftype,
                    title=f"Evidence issue: {ev_req_id}",
                    description=(
                        f"Evidence requirement {ev_req_id} is {state} and must be "
                        "remediated."
                    ),
                    severity=GovernanceSeverity.MEDIUM.value,
                    requirement_ids=[],
                    control_ids=[],
                    evidence_gap_ids=[ev_req_id] if ev_req_id else [],
                    reason_codes=[code, f"EVIDENCE_{state}"],
                    config=config,
                )
            )

    # --- Rule 4: policy-condition escalation of an otherwise-clean decision - #
    # Resolvable ONLY by an authority-verified human approval. Its dedicated
    # finding type (always remediation-ineligible) keeps it out of the
    # remediation / re-assessment rubber-stamp path.
    if not findings:
        approval = _escalation_approval_required(decision)
        if approval is not None:
            findings.append(
                _build_finding(
                    org=org,
                    decision=decision,
                    assessment=assessment,
                    finding_type=FindingType.ESCALATION_APPROVAL_REQUIRED.value,
                    title="Human approval required for escalated decision",
                    description=(
                        "A governance policy condition escalated this decision. "
                        "It can be resolved only by an authority-verified "
                        "approval from a principal holding approve authority for "
                        "this action — not by remediation evidence, a plain "
                        "review record, or re-assessment."
                    ),
                    severity=GovernanceSeverity.HIGH.value,
                    requirement_ids=[],
                    control_ids=[],
                    evidence_gap_ids=[],
                    reason_codes=[
                        "FINDING_ESCALATION_APPROVAL_REQUIRED",
                        *approval["reason_codes"],
                        *approval["condition_reason_codes"],
                    ],
                    config=config,
                )
            )

    # --- Fallback: branch applies but no specific finding was produced ----- #
    if not findings:
        findings.append(
            _build_finding(
                org=org,
                decision=decision,
                assessment=assessment,
                finding_type=FindingType.OTHER.value,
                title=f"Governance finding ({decision.outcome})",
                description=(
                    "The decision was not approved but no specific control or "
                    "evidence finding could be attributed."
                ),
                severity=GovernanceSeverity.MEDIUM.value,
                requirement_ids=[],
                control_ids=[],
                evidence_gap_ids=[],
                reason_codes=["FINDING_UNATTRIBUTED", f"DECISION_{decision.outcome}"],
                config=config,
            )
        )

    saved_findings = [repo.add(f) for f in findings]
    for finding in saved_findings:
        _emit_finding_created(db, org, finding)
    return saved_findings


def _emit_finding_created(db: Session, org: str, finding: Finding) -> None:
    """Publish a ``finding.created`` integration event (best-effort)."""
    from app.services.canonical.integration import event_publisher
    from app.services.canonical.integration.contracts import EventContract
    from app.utils.canonical_enums import IntegrationEventType

    event_publisher.emit_safe(
        db,
        EventContract(
            event_type=IntegrationEventType.FINDING_CREATED,
            organization_id=org,
            aggregate_type="Finding",
            aggregate_id=finding.id,
            references={
                "finding_id": finding.finding_id,
                "decision_id": finding.decision_id,
                "assessment_id": finding.assessment_id,
                "intent_id": finding.intent_id,
                "requirement_ids": _load(finding.requirement_ids, []) or [],
                "control_ids": _load(finding.control_ids, []) or [],
                "evidence_gap_ids": _load(finding.evidence_gap_ids, []) or [],
                "finding_hash": finding.finding_hash,
            },
            attributes={
                "status": finding.status,
                "severity": finding.severity,
                "finding_type": finding.finding_type,
                "decision_impact": finding.decision_impact,
                "remediation_eligibility": finding.remediation_eligibility,
                "terminal": finding.terminal,
            },
        ),
    )


# --------------------------------------------------------------------------- #
# Reads / mutations
# --------------------------------------------------------------------------- #
def get(db: Session, organization_id: str, resource_id: str) -> Optional[Finding]:
    return FindingRepository(db).get(organization_id, resource_id)


def list_(
    db: Session,
    organization_id: str,
    *,
    status: Optional[str] = None,
    finding_type: Optional[str] = None,
    decision_id: Optional[str] = None,
    intent_id: Optional[str] = None,
    owner: Optional[str] = None,
    skip: int = 0,
    limit: int = 100,
) -> Sequence[Finding]:
    return FindingRepository(db).list_filtered(
        organization_id,
        status=status,
        finding_type=finding_type,
        decision_id=decision_id,
        intent_id=intent_id,
        owner=owner,
        skip=skip,
        limit=limit,
    )


def assign(
    db: Session,
    organization_id: str,
    resource_id: str,
    *,
    owner: str,
    due_date=None,
) -> Optional[Finding]:
    """Assign a finding to an owner, moving OPEN -> ASSIGNED."""
    repo = FindingRepository(db)
    finding = repo.get(organization_id, resource_id)
    if finding is None:
        return None
    finding.owner = owner
    if due_date is not None:
        finding.due_date = due_date
    if finding.status == FindingStatus.OPEN.value:
        finding.status = FindingStatus.ASSIGNED.value
    return repo.save(finding)
