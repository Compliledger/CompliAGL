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

Priorities 10-13 read ``evidence_claims['EV-CIRCLE-LUSD-ASSURANCE']`` --
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

The four assurance reason codes are deliberately distinct so a DENIED
decision never implies the reserve requirement was *violated* when it
simply couldn't be assessed:

* ``REQUIRED_ASSURANCE_UNAVAILABLE`` -- the claim is missing entirely
  (``result is None``): CompliLedger was unreachable, or the connector
  otherwise produced no well-formed claim. Nothing was evaluated.
* ``REQUIRED_ASSURANCE_NOT_EVALUABLE`` -- CompliLedger answered but
  reports the control itself could not be evaluated (``result ==
  'NOT_EVALUABLE'``, e.g. evidence went ``EXPIRED``).
* ``REQUIRED_ASSURANCE_NOT_SATISFIED`` -- CompliLedger answered with any
  other non-satisfied result (``result not in ('SATISFIED',
  'NOT_EVALUABLE')``, chiefly ``NOT_SATISFIED`` itself). This is the only
  one of the four that means the reserve requirement was actually
  assessed and failed.
* ``REQUIRED_ASSURANCE_STALE`` -- CompliLedger reports the control
  ``SATISFIED`` but its continuous-monitoring status is not ``CURRENT``:
  the requirement was met as of the last check, but that check is stale.

Formal control: AGT-AUTH-001 (Agent Delegated Financial Authority)
------------------------------------------------------------------
``AGT-AUTH-001`` formally declares the requirement that the acting agent be
verified, not revoked, and act within its delegated financial authority
(``actor.metadata['delegated_authority']``). Delegated authority is
first-class actor context here, not evidence (docs/dev-rules.md rule 6) --
there is no evidence connector for it, and the control-evaluation stage's
expression engine only ever sees normalized evidence facts, never
``actor``/``intent`` (``control_evaluation_service._evidence_facts``, a
decision-engine file this package must not touch -- docs/dev-rules.md rule
2). So exactly like ``CTL-CIRCLE-LUSD-ASSURANCE`` above, this control's
``evaluation_expression`` is structural-only (trivially ``True``: it has no
evidence to gate on and is always reached SATISFIED) -- the actual
verified/not-revoked/in-scope judgment is expressed via the
``DC-AGT-AUTH-001-*`` terminal decision conditions below, priorities 20/30,
which are the only place actor/intent context is available to the
interpreter. The 10 USDC autonomous-limit check is a separate, unrelated
decision condition (priority 40, ``ESCALATED``) -- it is not part of this
control.
"""

from __future__ import annotations

from app.schemas.canonical.governance_package import (
    ExecutableGovernancePackageCreate,
)

PACKAGE_NAME = "circle-treasury-governed-action"
PACKAGE_VERSION = "1.1.0"

REQ_ASSURANCE = "REQ-CIRCLE-LUSD-ASSURANCE"
CTL_ASSURANCE = "CTL-CIRCLE-LUSD-ASSURANCE"
EV_ASSURANCE = "EV-CIRCLE-LUSD-ASSURANCE"

REQ_AGENT_AUTHORITY = "REQ-CIRCLE-AGENT-AUTHORITY"
CTL_AGENT_AUTHORITY = "AGT-AUTH-001"

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
            },
            {
                "requirement_id": REQ_AGENT_AUTHORITY,
                "source_reference": (
                    "Circle Grant MVP: a Treasury Agent may only act within "
                    "its delegated financial authority. Contract: "
                    "docs/circle-mvp-implementation-plan.md PR 3a, "
                    "docs/dev-rules.md rule 6."
                ),
                "normalized_text": (
                    "Before a treasury transfer is authorised, the acting "
                    "agent must be verified, not revoked, and the proposed "
                    "action/asset/network must fall within the agent's "
                    "delegated financial authority "
                    "(actor.metadata.delegated_authority)."
                ),
                "requirement_type": "agent_delegated_authority",
                "classification": "OBLIGATION",
                "mapped_control_ids": [CTL_AGENT_AUTHORITY],
            },
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
            },
            {
                "control_id": CTL_AGENT_AUTHORITY,
                "requirement_ids": [REQ_AGENT_AUTHORITY],
                "control_objective": (
                    "The Treasury Agent's identity is verified and not "
                    "revoked, and the proposed action/asset/network fall "
                    "within its delegated financial authority "
                    "(actor.metadata['delegated_authority']). Delegated "
                    "authority is first-class actor context, not evidence "
                    "(docs/dev-rules.md rule 6), so -- exactly like "
                    "CTL-CIRCLE-LUSD-ASSURANCE above -- this control's "
                    "evaluation_expression is structural only; the actual "
                    "verified/not-revoked/in-scope judgment is expressed via "
                    "the DC-AGT-AUTH-001-* terminal decision conditions, the "
                    "only place actor/intent context is available to the "
                    "interpreter. See module docstring."
                ),
                "evaluation_expression": "True",
                "mandatory": True,
                "severity": "HIGH",
                "failure_disposition": "DENY",
                "evidence_requirement_ids": [],
                "decision_impact": {
                    "title": "Agent Delegated Financial Authority",
                    "enforced_by": [
                        "DC-AGT-AUTH-001-NOT-VERIFIED",
                        "DC-AGT-AUTH-001-AUTHORITY-EXCEEDED",
                    ],
                },
            },
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
                "condition_id": "DC-CIRCLE-ASSURANCE-UNAVAILABLE",
                "expression": f"{_CLAIMS}['result'] == None",
                "resulting_decision": "DENIED",
                "priority": 10,
                "reason_code": "REQUIRED_ASSURANCE_UNAVAILABLE",
                "terminal": True,
            },
            {
                "condition_id": "DC-CIRCLE-ASSURANCE-NOT-EVALUABLE",
                "expression": f"{_CLAIMS}['result'] == 'NOT_EVALUABLE'",
                "resulting_decision": "DENIED",
                "priority": 11,
                "reason_code": "REQUIRED_ASSURANCE_NOT_EVALUABLE",
                "terminal": True,
            },
            {
                "condition_id": "DC-CIRCLE-ASSURANCE-NOT-SATISFIED",
                "expression": (
                    f"{_CLAIMS}['result'] != None and "
                    f"{_CLAIMS}['result'] != 'SATISFIED' and "
                    f"{_CLAIMS}['result'] != 'NOT_EVALUABLE'"
                ),
                "resulting_decision": "DENIED",
                "priority": 12,
                "reason_code": "REQUIRED_ASSURANCE_NOT_SATISFIED",
                "terminal": True,
            },
            {
                "condition_id": "DC-CIRCLE-ASSURANCE-STALE",
                "expression": f"{_CLAIMS}['monitoring_status'] != 'CURRENT'",
                "resulting_decision": "DENIED",
                "priority": 13,
                "reason_code": "REQUIRED_ASSURANCE_STALE",
                "terminal": True,
            },
            {
                "condition_id": "DC-AGT-AUTH-001-NOT-VERIFIED",
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
                "condition_id": "DC-AGT-AUTH-001-AUTHORITY-EXCEEDED",
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
