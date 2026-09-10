"""HarborStone governance package content.

Authors the executable governance package that turns on the CompliIdentity
authority-context integration for the HarborStone $250K AML/sanctions demo
scenario (``requires_authority_context: true``), per
``HARBORSTONE_GOVERNANCE_PACKAGE_DESIGN.md`` at the repo root.

Sanctions-screening control (package v1.2.1)
-------------------------------------------
The requirement/control pair ``REQ-HARBORSTONE-SANCTIONS-SCREENING`` /
``CTL-HARBORSTONE-SANCTIONS-SCREENING`` is real, keyed to SENTRY's structured
screening evidence (``EV-HARBORSTONE-SANCTIONS-SCREENING`` ->
``harborstone.sanctions_screening.v1``, served by
``connectors/harborstone_sentry_screening.py``). The screening *lookup* is a
deterministic in-repo demo dataset (project-owner-approved for the MVP, and
labelled as simulation on every evidence item) -- the control, the evidence
retrieval, its evaluation and the enforcement around it are real. This
replaces the retired ``*-PLACEHOLDER-SANCTIONS-SCREENING`` pair and its
env-gated placeholder connector -- see
``docs/harborstone-sanctions-screening.md``.

Screening routing:

* ``CTL-HARBORSTONE-SANCTIONS-SCREENING`` (mandatory) is SATISFIED only on a
  clean screen (``result == "NO_MATCH"``); anything else makes the assessment
  ``NOT_SATISFIED``.
* ``DC-HARBORSTONE-SANCTIONS-CONFIRMED`` (priority 11) turns a
  ``CONFIRMED_MATCH`` into a terminal ``DENIED``.
* ``DC-HARBORSTONE-SANCTIONS-REVIEW`` (priority 12) turns any screening result
  flagged ``requires_human_review`` (i.e. ``POTENTIAL_MATCH``) into
  ``ESCALATED`` -- with a ``NOT_SATISFIED`` assessment the engine's
  ``_resolve_outcome`` maps ``NOT_SATISFIED + ESCALATED condition`` to
  ``ESCALATED`` (``CONTROL_REMEDIATION_REQUIRED``) rather than a hard deny.

Both screening conditions read ``evidence_claims[<EV id>]`` -- the normalized
screening claims, surfaced into the decision context by
``decision_service`` (generic mechanism; mirrors
``control_evaluation_service``'s evidence-fact vocabulary).

The decision conditions below are the real, reviewed design from
``HARBORSTONE_GOVERNANCE_PACKAGE_DESIGN.md`` (amount-units bug already
caught and fixed there -- see that doc's "Resolved" item 3): they reference
``intent.amount_minor`` (integer minor units, e.g. cents), not
``intent.parameters.amount``, and match the exact field
``authority_context_service._authority_request_params()`` already sends to
CompliIdentity, so the probe and the threshold never disagree.

Package v1.1.0 added the human-approval re-decision path
(``DC-HARBORSTONE-APPROVED-VIA-HUMAN`` + a guard on
``DC-HARBORSTONE-HUMAN-APPROVAL``): once ``escalation_approval_service``
records an authority-verified approval and a re-decision runs, the engine
exposes it as the ``approval`` runtime fact and the escalation upgrades to
APPROVED, with the prior ESCALATED decision preserved and superseded. See
that design doc's 2026-09-06 "human-approval re-decision" Resolved section.

The ``authority.reason`` values the DENIED / ESCALATED conditions test are
CompliIdentity's real finding codes, confirmed against 13 live
authority-context responses (see
``docs/COMPLIIDENTITY_CONTRACT_VOCABULARY_CONFIRMED.md``):
``permission_missing`` / ``delegation_revoked`` / ``principal_not_active`` /
``resource_scope_unmatched`` are hard denials; ``approval_required`` is the
escalation. ``credential_expired`` -- in an earlier draft's DENIED list --
does not exist in CompliIdentity's model and was removed.
``resource_scope_unmatched`` (delegate reaching outside the case its grant
is scoped to) was *observed firing* in the acceptance run and added.
``authority.reason`` is a single derived code
(``authority_context_service._derive_reason``); the ESCALATED condition
also tests the raw ``authority.approval_required`` boolean so it holds even
if the derivation priority ever changes.

Deliberately **not included**: an ``assessment.overall_result ==
"SATISFIED"`` clause on the APPROVED condition. The design doc's own
pseudocode used a bare ``assessment == SATISFIED``, but ``assessment`` in
the real decision context is a dict (``{"overall_result": ..., ...}``), not
a string -- that comparison would never have matched, the same class of bug
as the amount-field issue. It's also redundant: ``decision_service.
_resolve_outcome()`` already gates the APPROVED branch behind a SATISFIED
assessment structurally, regardless of what a package's own decision
condition says, so a NOT_SATISFIED assessment can never reach APPROVED here
even without repeating the check in the package.
"""

from __future__ import annotations

from app.schemas.canonical.governance_package import (
    ExecutableGovernancePackageCreate,
)

PACKAGE_NAME = "harborstone-aml-sanctions-screening"
# 1.2.1 replaces the placeholder screening requirement/control with a real
# pair keyed to SENTRY's structured screening evidence
# (harborstone.sanctions_screening.v1), and adds two screening decision
# conditions (DC-HARBORSTONE-SANCTIONS-CONFIRMED / -REVIEW). The
# DENIED / plain-ESCALATED / clean-APPROVE / human-approval paths are
# unchanged for every case whose screen comes back NO_MATCH.
PACKAGE_VERSION = "1.2.1"

REQ_SCREENING = "REQ-HARBORSTONE-SANCTIONS-SCREENING"
CTL_SCREENING = "CTL-HARBORSTONE-SANCTIONS-SCREENING"
EV_SCREENING = "EV-HARBORSTONE-SANCTIONS-SCREENING"

# The evidence_type the screening connector serves (must match
# connectors/harborstone_sentry_screening.py).
SCREENING_EVIDENCE_TYPE = "harborstone.sanctions_screening.v1"
SCREENING_ISSUER = "sentry.harborstone.compliagl"

# USD $250,000.00 in integer minor units (cents). USD uses a 2-decimal-place
# minor unit (major * 100) -- not universal across currencies, which is why
# every condition below also guards on amount_currency == "USD".
AMOUNT_THRESHOLD_MINOR = 25_000_000

# CompliIdentity's real hard-denial finding codes (confirmed against 13 live
# authority-context responses -- see COMPLIIDENTITY_CONTRACT_VOCABULARY_
# CONFIRMED.md). `approval_required` is deliberately NOT here -- it is the
# escalation, not a denial.
_AUTHORITY_DENY_REASONS = [
    "permission_missing",
    "delegation_revoked",
    "principal_not_active",
    "resource_scope_unmatched",
    "limit_exceeded",
]

# A currently-valid, authority-verified human approval, as the `approval`
# runtime fact (decision_service loads it only for a re-decision -- see
# runtime_facts.build_approval_facts). Absent `approval` key -> every clause is
# `None == True` -> False, so this reads as "no valid approval" on a first
# decision without raising.
_APPROVAL_IS_VALID = (
    "approval.present == True and "
    "approval.approver_authorized == True and "
    "approval.expired == False"
)

# The normalized screening claims, as surfaced into the decision context by
# decision_service (decision_context["evidence_claims"][<EV id>]).
_SCREENING_CLAIMS = f"evidence_claims['{EV_SCREENING}']"


def build_harborstone_package(
    organization_id: str,
) -> ExecutableGovernancePackageCreate:
    """Return the (not-yet-published) HarborStone package create payload.

    Caller is responsible for running it through the real lifecycle
    (``governance_package_service.create`` -> ``validate`` -> ``approve`` ->
    ``publish``) -- this function only builds the content.
    """
    return ExecutableGovernancePackageCreate(
        organization_id=organization_id,
        package_name=PACKAGE_NAME,
        package_version=PACKAGE_VERSION,
        requires_authority_context=True,
        requirements=[
            {
                "requirement_id": REQ_SCREENING,
                "source_reference": (
                    "HarborStone AML program: mandatory sanctions screening of "
                    "the counterparty before any value transfer is authorised. "
                    "Evidence contract: docs/harborstone-sanctions-screening.md "
                    "(demo3.sanctions-screening.v1)."
                ),
                "normalized_text": (
                    "Before an AML-case value transfer is authorised, the "
                    "counterparty must be screened against sanctions lists by "
                    "the SENTRY screening agent. A confirmed match blocks the "
                    "transfer; a potential match requires human review; only a "
                    "clean screen (NO_MATCH) may proceed automatically."
                ),
                "requirement_type": "aml_sanctions_screening",
                "classification": "OBLIGATION",
                "mapped_control_ids": [CTL_SCREENING],
            }
        ],
        control_definitions=[
            {
                "control_id": CTL_SCREENING,
                "requirement_ids": [REQ_SCREENING],
                "control_objective": (
                    "The counterparty's sanctions screening came back clean "
                    "(result == NO_MATCH). A POTENTIAL_MATCH or CONFIRMED_MATCH "
                    "makes this control NOT_SATISFIED; the screening decision "
                    "conditions then route the outcome to ESCALATED (human "
                    "review) or DENIED (confirmed match)."
                ),
                "evaluation_expression": (
                    f"evidence['{EV_SCREENING}']['claims']['result'] "
                    "== 'NO_MATCH'"
                ),
                "mandatory": True,
                "severity": "HIGH",
                "failure_disposition": "DENY",
                "evidence_requirement_ids": [EV_SCREENING],
            }
        ],
        evidence_requirements=[
            {
                "evidence_requirement_id": EV_SCREENING,
                "control_ids": [CTL_SCREENING],
                "evidence_type": SCREENING_EVIDENCE_TYPE,
                "authoritative_source_type": "EXTERNAL_APPLICATION",
                # The screened party is the transaction counterparty, so the
                # evidence subject binds to the Target's external identifier
                # (the account/wallet actually being screened), not the
                # requesting agent.
                "subject_binding": "target",
                "freshness_requirement": "P7D",
                "validation_method": "signature_verification",
                "allowed_issuers": [SCREENING_ISSUER],
                "minimum_cardinality": 1,
                "mandatory": True,
            }
        ],
        decision_conditions=[
            {
                "condition_id": "DC-HARBORSTONE-AUTHORITY-DENIED",
                "expression": (
                    f"authority.reason in {_AUTHORITY_DENY_REASONS!r}"
                ),
                "resulting_decision": "DENIED",
                "priority": 10,
                "reason_code": "AUTHORITY_DENIED",
                "terminal": True,
            },
            {
                # A confirmed sanctions hit is a hard block, checked right
                # after the authority hard-denials and before anything that
                # could approve or escalate.
                "condition_id": "DC-HARBORSTONE-SANCTIONS-CONFIRMED",
                "expression": (
                    f"{_SCREENING_CLAIMS}['result'] == 'CONFIRMED_MATCH'"
                ),
                "resulting_decision": "DENIED",
                "priority": 11,
                "reason_code": "SANCTIONS_CONFIRMED_MATCH",
                "terminal": True,
            },
            {
                # A screening result flagged for human review (POTENTIAL_MATCH)
                # escalates. The mandatory control is already NOT_SATISFIED for
                # this case, so _resolve_outcome maps NOT_SATISFIED + this
                # ESCALATED condition to ESCALATED (not a hard deny).
                "condition_id": "DC-HARBORSTONE-SANCTIONS-REVIEW",
                "expression": (
                    f"{_SCREENING_CLAIMS}['requires_human_review'] == True"
                ),
                "resulting_decision": "ESCALATED",
                "priority": 12,
                "reason_code": "SANCTIONS_HUMAN_REVIEW_REQUIRED",
                "terminal": True,
            },
            {
                # Re-decision path: a valid, authority-verified human approval
                # upgrades the escalation. Priority 15 -> checked before
                # DC-HARBORSTONE-HUMAN-APPROVAL (20) but after the hard-denial
                # and screening conditions (10-12). The `not in` guard is
                # belt-and-suspenders: priority 10 being terminal already means
                # a hard denial never reaches here.
                "condition_id": "DC-HARBORSTONE-APPROVED-VIA-HUMAN",
                "expression": (
                    f"{_APPROVAL_IS_VALID} and "
                    f"authority.reason not in {_AUTHORITY_DENY_REASONS!r}"
                ),
                "resulting_decision": "APPROVED",
                "priority": 15,
                "reason_code": "HARBORSTONE_APPROVED_VIA_HUMAN",
                "terminal": True,
            },
            {
                "condition_id": "DC-HARBORSTONE-HUMAN-APPROVAL",
                "expression": (
                    "(authority.reason == 'approval_required' or "
                    "authority.approval_required == True or "
                    "(intent.amount_currency == 'USD' and "
                    f"intent.amount_minor >= {AMOUNT_THRESHOLD_MINOR})) "
                    f"and not ({_APPROVAL_IS_VALID})"
                ),
                "resulting_decision": "ESCALATED",
                "priority": 20,
                "reason_code": "HUMAN_APPROVAL_REQUIRED",
                "terminal": True,
            },
            {
                "condition_id": "DC-HARBORSTONE-APPROVE",
                "expression": (
                    "authority.sufficient == True and "
                    "intent.amount_currency == 'USD' and "
                    f"intent.amount_minor < {AMOUNT_THRESHOLD_MINOR}"
                ),
                "resulting_decision": "APPROVED",
                "priority": 100,
                "reason_code": "HARBORSTONE_APPROVED",
                "terminal": True,
            },
        ],
        metadata={
            "demo": "harborstone",
            "sanctions_screening": "simulated-demo-dataset",
        },
    )
