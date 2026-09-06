"""HarborStone governance package content.

Authors the executable governance package that turns on the CompliIdentity
authority-context integration for the HarborStone $250K AML/sanctions demo
scenario (``requires_authority_context: true``), per
``HARBORSTONE_GOVERNANCE_PACKAGE_DESIGN.md`` at the repo root.

**Contains a placeholder screening control.** The requirement/control pair
named ``REQ-PLACEHOLDER-SANCTIONS-SCREENING`` /
``CTL-PLACEHOLDER-SANCTIONS-SCREENING`` does not evaluate any real
sanctions-screening signal -- its ``evaluation_expression`` is trivially
``"True"``. It exists only so this package is structurally valid (a package
cannot publish without at least one requirement and one mandatory control)
and so the decision-engine wiring below it can be exercised end-to-end. It
must be replaced with real screening-control content before any actual
HarborStone demo run. See ``PENDING_REVIEW_harborstone_screening_control_
placeholder.md`` at the repo root for what replaces it and why it isn't
designed yet.

The three decision conditions below are the real, reviewed design from
``HARBORSTONE_GOVERNANCE_PACKAGE_DESIGN.md`` (amount-units bug already
caught and fixed there -- see that doc's "Resolved" item 3): they reference
``intent.amount_minor`` (integer minor units, e.g. cents), not
``intent.parameters.amount``, and match the exact field
``authority_context_service._authority_request_params()`` already sends to
CompliIdentity, so the probe and the threshold never disagree.

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
PACKAGE_VERSION = "1.0.0"

REQ_PLACEHOLDER_SCREENING = "REQ-PLACEHOLDER-SANCTIONS-SCREENING"
CTL_PLACEHOLDER_SCREENING = "CTL-PLACEHOLDER-SANCTIONS-SCREENING"
EV_PLACEHOLDER_SCREENING = "EV-PLACEHOLDER-SANCTIONS-SCREENING"

# USD $250,000.00 in integer minor units (cents). USD uses a 2-decimal-place
# minor unit (major * 100) -- not universal across currencies, which is why
# every condition below also guards on amount_currency == "USD".
AMOUNT_THRESHOLD_MINOR = 25_000_000


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
                "requirement_id": REQ_PLACEHOLDER_SCREENING,
                "source_reference": (
                    "PLACEHOLDER -- no real source yet; see "
                    "PENDING_REVIEW_harborstone_screening_control_placeholder.md"
                ),
                "normalized_text": (
                    "PLACEHOLDER stand-in for HarborStone's real AML/"
                    "sanctions-screening requirement. Not real compliance "
                    "content -- must not be used in a real demo run."
                ),
                "requirement_type": "aml_sanctions_screening_placeholder",
                "classification": "OBLIGATION",
                "mapped_control_ids": [CTL_PLACEHOLDER_SCREENING],
            }
        ],
        control_definitions=[
            {
                "control_id": CTL_PLACEHOLDER_SCREENING,
                "requirement_ids": [REQ_PLACEHOLDER_SCREENING],
                "control_objective": (
                    "PLACEHOLDER -- stands in for real sanctions-screening "
                    "pass/fail logic pending SENTRY integration design. "
                    "evaluation_expression is trivially True; it does not "
                    "evaluate any real screening signal."
                ),
                "evaluation_expression": "True",
                "mandatory": True,
                "severity": "HIGH",
                "failure_disposition": "DENY",
                "evidence_requirement_ids": [EV_PLACEHOLDER_SCREENING],
            }
        ],
        evidence_requirements=[
            {
                "evidence_requirement_id": EV_PLACEHOLDER_SCREENING,
                "control_ids": [CTL_PLACEHOLDER_SCREENING],
                "evidence_type": "harborstone.sanctions_screening_placeholder",
                "authoritative_source_type": "EXTERNAL_APPLICATION",
                "subject_binding": "actor",
                "freshness_requirement": "P36500D",
                "validation_method": "signature_verification",
                "allowed_issuers": ["harborstone-screening-placeholder.example"],
                "minimum_cardinality": 1,
                "mandatory": True,
            }
        ],
        decision_conditions=[
            {
                "condition_id": "DC-HARBORSTONE-AUTHORITY-DENIED",
                "expression": (
                    "authority.reason in ['permission_missing', "
                    "'delegation_revoked', 'principal_not_active', "
                    "'resource_scope_unmatched', 'limit_exceeded']"
                ),
                "resulting_decision": "DENIED",
                "priority": 10,
                "reason_code": "AUTHORITY_DENIED",
                "terminal": True,
            },
            {
                "condition_id": "DC-HARBORSTONE-HUMAN-APPROVAL",
                "expression": (
                    "authority.reason == 'approval_required' or "
                    "authority.approval_required == True or "
                    "(intent.amount_currency == 'USD' and "
                    f"intent.amount_minor >= {AMOUNT_THRESHOLD_MINOR})"
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
            "placeholder_screening_control": True,
        },
    )
