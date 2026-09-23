"""Circle treasury governance package content.

Authors the executable governance package that gates a Circle Treasury
Agent's USDC transfer proposals on CompliLedger's live continuous-assurance
state for the GENIUS LUSD reserve control, per
``docs/circle-mvp-implementation-plan.md`` PR 3a.

``requires_authority_context`` is deliberately False [D5]: delegated
authority for this MVP lives entirely in the Treasury Agent's
``identity_metadata.delegated_authority`` (see ``seed.py``); CompliIdentity
is never called (docs/dev-rules.md rule 6).

Mandatory assurance evidence, structural control (docs/dev-rules.md rule 4)
------------------------------------------------------------------------
``CTL-CIRCLE-LUSD-ASSURANCE``'s ``evaluation_expression`` checks only that
CompliLedger answered about the right control (``claims['control_id']``) --
never the assurance ``result``/``monitoring_status`` fields. Evidence
sufficiency (issuer trust, freshness, cardinality) already gates the control
before the expression ever runs (see ``control_evaluation_service.
_gate_on_sufficiency``), so the control is SATISFIED whenever the connector
returns *any* well-formed claim -- healthy or degraded. This keeps
"assurance is degraded" a decision-condition fact, not an assessment
failure: a degraded claim must DENY via a terminal package condition, never
via the engine auto-escalating a NOT_SATISFIED/NOT_EVALUABLE assessment
(docs/dev-rules.md rule 4).

Priorities 10-12 read ``evidence_claims['EV-CIRCLE-LUSD-ASSURANCE']`` --
the normalized assurance claim, surfaced into the decision context by
``decision_service`` (the same generic mechanism HarborStone's package
uses). They fire correctly even when the connector produced no claim at all
(CompliLedger unreachable): ``package_interpreter``'s subscript resolution
returns ``None`` on a missing key at every nesting level (confirmed by
reading ``package_interpreter.py`` directly -- a missing key is caught as
``KeyError``/``TypeError`` inside the interpreter and returns ``None``, it
never raises ``ExpressionError``), so
``evidence_claims['EV-CIRCLE-LUSD-ASSURANCE']['result'] == None`` is
``True`` whether the key is absent or the claim's ``result`` field is
literally missing. And because ``decision_service._resolve_outcome``
checks ``condition_outcome == DENIED`` before any assessment-outcome
branch, a matched terminal DENIED condition here wins regardless of
whatever the assessment itself ends up being.
"""

from __future__ import annotations

from app.schemas.canonical.governance_package import (
    ExecutableGovernancePackageCreate,
)

PACKAGE_NAME = "circle-treasury-governed-action"
PACKAGE_VERSION = "1.0.0"

REQ_ASSURANCE = "REQ-CIRCLE-LUSD-ASSURANCE"
CTL_ASSURANCE = "CTL-CIRCLE-LUSD-ASSURANCE"
EV_ASSURANCE = "EV-CIRCLE-LUSD-ASSURANCE"

# Must match connectors/compliledger_assurance.py.
ASSURANCE_EVIDENCE_TYPE = "compliledger.assurance_state.v1"
ASSURANCE_ISSUER = "compliledger.assurance-state"
ASSURANCE_CONTROL_ID = "GENIUS-LUSD-RESERVE-001"

# USDC minor units (6 decimals): 5 USDC = 5_000_000, cap = 10 USDC (docs/dev-rules.md rule 7).
AUTONOMOUS_LIMIT_MINOR = 10_000_000

_CLAIMS = f"evidence_claims['{EV_ASSURANCE}']"
_DELEGATED = "actor.metadata['delegated_authority']"


def build_circle_treasury_package(
    organization_id: str,
) -> ExecutableGovernancePackageCreate:
    """Return the (not-yet-published) Circle treasury package create payload.

    Caller is responsible for running it through the real lifecycle
    (``governance_package_service.create`` -> ``validate`` -> ``approve`` ->
    ``publish``) -- this function only builds the content.
    """
    return ExecutableGovernancePackageCreate(
        organization_id=organization_id,
        package_name=PACKAGE_NAME,
        package_version=PACKAGE_VERSION,
        requires_authority_context=False,
        requirements=[
            {
                "requirement_id": REQ_ASSURANCE,
                "source_reference": (
                    "Circle Grant MVP: a Treasury Agent's USDC transfer may "
                    "only be authorized while CompliLedger's continuous "
                    "assurance for the GENIUS LUSD reserve control is "
                    "currently satisfied. Contract: "
                    "docs/circle-mvp-implementation-plan.md PR 2/3a."
                ),
                "normalized_text": (
                    "Before a treasury transfer is authorised, the current "
                    "assurance state of the GENIUS LUSD reserve control must "
                    "be fetched live from CompliLedger. Any degraded or "
                    "unavailable assurance state blocks the transfer."
                ),
                "requirement_type": "continuous_assurance",
                "classification": "OBLIGATION",
                "mapped_control_ids": [CTL_ASSURANCE],
            }
        ],
        control_definitions=[
            {
                "control_id": CTL_ASSURANCE,
                "requirement_ids": [REQ_ASSURANCE],
                "control_objective": (
                    "CompliLedger answered the live assurance/state query for "
                    "the GENIUS LUSD reserve control. Whether that answer is "
                    "healthy or degraded is a decision-condition fact, not a "
                    "control failure -- see module docstring."
                ),
                "evaluation_expression": (
                    f"evidence['{EV_ASSURANCE}']['claims']['control_id'] "
                    f"== '{ASSURANCE_CONTROL_ID}'"
                ),
                "mandatory": True,
                "severity": "HIGH",
                "failure_disposition": "DENY",
                "evidence_requirement_ids": [EV_ASSURANCE],
            }
        ],
        evidence_requirements=[
            {
                "evidence_requirement_id": EV_ASSURANCE,
                "control_ids": [CTL_ASSURANCE],
                "evidence_type": ASSURANCE_EVIDENCE_TYPE,
                "authoritative_source_type": "EXTERNAL_APPLICATION",
                "freshness_requirement": "PT1H",
                "validation_method": "trusted_issuer",
                "allowed_issuers": [ASSURANCE_ISSUER],
                "minimum_cardinality": 1,
                "mandatory": True,
            }
        ],
        decision_conditions=[
            {
                "condition_id": "DC-CIRCLE-ASSURANCE-MISSING",
                "expression": f"{_CLAIMS}['result'] == None",
                "resulting_decision": "DENIED",
                "priority": 10,
                "reason_code": "REQUIRED_ASSURANCE_NOT_SATISFIED",
                "terminal": True,
            },
            {
                "condition_id": "DC-CIRCLE-ASSURANCE-NOT-EVALUABLE",
                "expression": (
                    f"{_CLAIMS}['result'] != None and "
                    f"{_CLAIMS}['result'] != 'SATISFIED'"
                ),
                "resulting_decision": "DENIED",
                "priority": 11,
                "reason_code": "REQUIRED_ASSURANCE_NOT_EVALUABLE",
                "terminal": True,
            },
            {
                "condition_id": "DC-CIRCLE-ASSURANCE-STALE",
                "expression": f"{_CLAIMS}['monitoring_status'] != 'CURRENT'",
                "resulting_decision": "DENIED",
                "priority": 12,
                "reason_code": "REQUIRED_ASSURANCE_STALE",
                "terminal": True,
            },
            {
                "condition_id": "DC-CIRCLE-ACTOR-NOT-VERIFIED",
                "expression": (
                    "actor.verification_status != 'VERIFIED' or "
                    "actor.revocation_status == 'REVOKED'"
                ),
                "resulting_decision": "DENIED",
                "priority": 20,
                "reason_code": "ACTOR_NOT_VERIFIED",
                "terminal": True,
            },
            {
                "condition_id": "DC-CIRCLE-DELEGATED-AUTHORITY-EXCEEDED",
                "expression": (
                    f"intent.action not in {_DELEGATED}['allowed_actions'] or "
                    f"intent.parameters['asset'] not in {_DELEGATED}['allowed_assets'] or "
                    f"intent.parameters['network'] not in {_DELEGATED}['allowed_networks']"
                ),
                "resulting_decision": "DENIED",
                "priority": 30,
                "reason_code": "DELEGATED_AUTHORITY_EXCEEDED",
                "terminal": True,
            },
            {
                "condition_id": "DC-CIRCLE-AUTONOMOUS-LIMIT-EXCEEDED",
                "expression": (
                    f"intent.amount_minor > {_DELEGATED}['autonomous_limit_minor']"
                ),
                "resulting_decision": "ESCALATED",
                "priority": 40,
                "reason_code": "AUTONOMOUS_LIMIT_EXCEEDED",
                "terminal": True,
            },
            {
                "condition_id": "DC-CIRCLE-APPROVE",
                "expression": (
                    f"{_CLAIMS}['result'] == 'SATISFIED' and "
                    f"{_CLAIMS}['monitoring_status'] == 'CURRENT' and "
                    "actor.verification_status == 'VERIFIED' and "
                    "actor.revocation_status != 'REVOKED' and "
                    f"intent.action in {_DELEGATED}['allowed_actions'] and "
                    f"intent.parameters['asset'] in {_DELEGATED}['allowed_assets'] and "
                    f"intent.parameters['network'] in {_DELEGATED}['allowed_networks'] and "
                    f"intent.amount_minor <= {_DELEGATED}['autonomous_limit_minor']"
                ),
                "resulting_decision": "APPROVED",
                "priority": 50,
                "reason_code": "AUTHORIZED_WITHIN_LIMIT",
                "terminal": True,
            },
        ],
        metadata={
            "demo": "circle-mvp",
            "assurance_target_id": "target_lusd",
            "assurance_control_id": ASSURANCE_CONTROL_ID,
        },
    )
