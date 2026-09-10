"""Tests for the HarborStone governance package content.

Guards the decision-condition semantics against regression -- in particular
the 2026-09-06 corrections made against CompliIdentity's real finding
vocabulary (``credential_expired`` removed, ``resource_scope_unmatched``
added, raw ``authority.approval_required`` boolean clause added). See
``docs/COMPLIIDENTITY_CONTRACT_VOCABULARY_CONFIRMED.md``.
"""

from __future__ import annotations

import pytest

from app.db.harborstone_package import (
    AMOUNT_THRESHOLD_MINOR,
    CTL_SCREENING,
    EV_SCREENING,
    PACKAGE_VERSION,
    build_harborstone_package,
)
from app.services.canonical.package_interpreter import (
    DeterministicPackageInterpreter,
    evaluate_expression,
)


@pytest.fixture(scope="module")
def conditions():
    package = build_harborstone_package("harborstone-demo")
    out = []
    for cond in package.decision_conditions:
        out.append(cond.model_dump() if hasattr(cond, "model_dump") else dict(cond))
    return out


def _fire(conditions, context):
    return [
        c["condition_id"]
        for c in conditions
        if evaluate_expression(c["expression"], context)
    ]


def _decide(conditions, context):
    """The priority-ordered, terminal-aware outcome (what the engine does)."""
    result = DeterministicPackageInterpreter().interpret(
        {"decision_conditions": conditions}, context
    )
    return result.decision, result.matched_condition_id


_ESCALATED_250K = {
    "authority": {
        "reason": "approval_required",
        "approval_required": True,
        "sufficient": False,
    },
    "intent": {"amount_currency": "USD", "amount_minor": AMOUNT_THRESHOLD_MINOR},
}


def test_package_opts_into_authority_context():
    package = build_harborstone_package("harborstone-demo")
    assert package.requires_authority_context is True


def test_package_version_is_current():
    assert PACKAGE_VERSION == "1.2.1"
    assert build_harborstone_package("harborstone-demo").package_version == "1.2.1"


# --------------------------------------------------------------------------- #
# Real sanctions-screening control + routing (package v1.2.1)
# --------------------------------------------------------------------------- #
def _control_expr():
    package = build_harborstone_package("harborstone-demo")
    ctl = next(
        c.model_dump() if hasattr(c, "model_dump") else dict(c)
        for c in package.control_definitions
        if (c.model_dump() if hasattr(c, "model_dump") else dict(c))["control_id"]
        == CTL_SCREENING
    )
    return ctl["evaluation_expression"]


def _control_facts(result):
    return {"evidence": {EV_SCREENING: {"claims": {"result": result}}}}


@pytest.mark.parametrize(
    "result,satisfied",
    [
        ("NO_MATCH", True),
        ("POTENTIAL_MATCH", False),
        ("CONFIRMED_MATCH", False),
        ("NOT_EVALUABLE", False),
    ],
)
def test_screening_control_satisfied_only_on_no_match(result, satisfied):
    assert bool(evaluate_expression(_control_expr(), _control_facts(result))) is satisfied


def _screening_ctx(result, *, requires_human_review, sufficient=True, amount=100):
    return {
        "authority": {
            "reason": None,
            "approval_required": False,
            "sufficient": sufficient,
        },
        "intent": {"amount_currency": "USD", "amount_minor": amount},
        "evidence_claims": {
            EV_SCREENING: {
                "result": result,
                "requires_human_review": requires_human_review,
            }
        },
    }


def test_confirmed_match_is_a_hard_denial(conditions):
    ctx = _screening_ctx("CONFIRMED_MATCH", requires_human_review=True)
    assert _decide(conditions, ctx) == (
        "DENIED",
        "DC-HARBORSTONE-SANCTIONS-CONFIRMED",
    )


def test_potential_match_escalates_for_human_review(conditions):
    ctx = _screening_ctx("POTENTIAL_MATCH", requires_human_review=True)
    assert _decide(conditions, ctx) == (
        "ESCALATED",
        "DC-HARBORSTONE-SANCTIONS-REVIEW",
    )


def test_clean_screen_does_not_trigger_a_screening_condition(conditions):
    ctx = _screening_ctx("NO_MATCH", requires_human_review=False)
    fired = _fire(conditions, ctx)
    assert "DC-HARBORSTONE-SANCTIONS-CONFIRMED" not in fired
    assert "DC-HARBORSTONE-SANCTIONS-REVIEW" not in fired
    assert _decide(conditions, ctx) == ("APPROVED", "DC-HARBORSTONE-APPROVE")


def test_authority_hard_denial_outranks_a_screening_confirmed_match(conditions):
    ctx = _screening_ctx("CONFIRMED_MATCH", requires_human_review=True)
    ctx["authority"]["reason"] = "permission_missing"
    assert _decide(conditions, ctx) == (
        "DENIED",
        "DC-HARBORSTONE-AUTHORITY-DENIED",
    )


def test_missing_screening_claims_fail_closed(conditions):
    # No evidence_claims key at all -> screening conditions are non-matching,
    # never raise.
    ctx = {
        "authority": {"reason": None, "approval_required": False, "sufficient": True},
        "intent": {"amount_currency": "USD", "amount_minor": 100},
    }
    fired = _fire(conditions, ctx)
    assert "DC-HARBORSTONE-SANCTIONS-CONFIRMED" not in fired
    assert "DC-HARBORSTONE-SANCTIONS-REVIEW" not in fired


def test_denied_list_matches_confirmed_vocabulary(conditions):
    denied = next(
        c for c in conditions if c["condition_id"] == "DC-HARBORSTONE-AUTHORITY-DENIED"
    )
    expr = denied["expression"]
    for code in (
        "permission_missing",
        "delegation_revoked",
        "principal_not_active",
        "resource_scope_unmatched",
        "limit_exceeded",
    ):
        assert f"'{code}'" in expr
    # credential_expired does not exist in CompliIdentity's model -- must not
    # have crept back in.
    assert "credential_expired" not in expr


@pytest.mark.parametrize(
    "reason",
    [
        "permission_missing",
        "delegation_revoked",
        "principal_not_active",
        "resource_scope_unmatched",
        "limit_exceeded",
    ],
)
def test_hard_denial_reasons_trigger_denied(conditions, reason):
    ctx = {
        "authority": {"reason": reason, "approval_required": False, "sufficient": False},
        "intent": {"amount_currency": "USD", "amount_minor": 100},
    }
    assert _fire(conditions, ctx) == ["DC-HARBORSTONE-AUTHORITY-DENIED"]


def test_approval_required_boolean_alone_triggers_escalation(conditions):
    """Even with `authority.reason` unset, the raw boolean escalates."""
    ctx = {
        "authority": {"reason": None, "approval_required": True, "sufficient": False},
        "intent": {"amount_currency": "USD", "amount_minor": 100},
    }
    assert _fire(conditions, ctx) == ["DC-HARBORSTONE-HUMAN-APPROVAL"]


def test_amount_threshold_alone_triggers_escalation(conditions):
    ctx = {
        "authority": {"reason": None, "approval_required": False, "sufficient": True},
        "intent": {"amount_currency": "USD", "amount_minor": AMOUNT_THRESHOLD_MINOR},
    }
    assert _fire(conditions, ctx) == ["DC-HARBORSTONE-HUMAN-APPROVAL"]


def test_clean_sub_threshold_transfer_approves(conditions):
    ctx = {
        "authority": {"reason": None, "approval_required": False, "sufficient": True},
        "intent": {
            "amount_currency": "USD",
            "amount_minor": AMOUNT_THRESHOLD_MINOR - 1,
        },
    }
    assert _fire(conditions, ctx) == ["DC-HARBORSTONE-APPROVE"]


def test_non_usd_does_not_match_amount_clause(conditions):
    """The USD guard means a large EUR amount falls through to neither the
    escalate nor the approve condition (engine fail-closes to DENIED)."""
    ctx = {
        "authority": {"reason": None, "approval_required": False, "sufficient": True},
        "intent": {"amount_currency": "EUR", "amount_minor": 999_999_999},
    }
    assert _fire(conditions, ctx) == []


# --------------------------------------------------------------------------- #
# Human-approval re-decision path (package v1.1.0)
# --------------------------------------------------------------------------- #
def _approval(*, expired=False, authorized=True):
    return {
        "approval": {
            "present": True,
            "approver_authorized": authorized,
            "expired": expired,
        }
    }


def test_first_decision_without_approval_fact_still_escalates(conditions):
    # No `approval` key -> the guard clause reads as "no valid approval" and
    # the escalation still fires; the new APPROVED-VIA-HUMAN condition does not.
    assert _decide(conditions, _ESCALATED_250K) == (
        "ESCALATED",
        "DC-HARBORSTONE-HUMAN-APPROVAL",
    )


def test_valid_approval_upgrades_escalation_to_approved(conditions):
    ctx = {**_ESCALATED_250K, **_approval()}
    assert _decide(conditions, ctx) == (
        "APPROVED",
        "DC-HARBORSTONE-APPROVED-VIA-HUMAN",
    )
    # The guard also suppresses the escalation condition from matching at all.
    assert "DC-HARBORSTONE-HUMAN-APPROVAL" not in _fire(conditions, ctx)


def test_expired_approval_does_not_upgrade(conditions):
    ctx = {**_ESCALATED_250K, **_approval(expired=True)}
    assert _decide(conditions, ctx) == (
        "ESCALATED",
        "DC-HARBORSTONE-HUMAN-APPROVAL",
    )
    assert "DC-HARBORSTONE-APPROVED-VIA-HUMAN" not in _fire(conditions, ctx)


def test_approval_never_overrides_a_hard_denial(conditions):
    ctx = {
        "authority": {
            "reason": "permission_missing",
            "approval_required": False,
            "sufficient": False,
        },
        "intent": {"amount_currency": "USD", "amount_minor": AMOUNT_THRESHOLD_MINOR},
        **_approval(),
    }
    assert _decide(conditions, ctx) == (
        "DENIED",
        "DC-HARBORSTONE-AUTHORITY-DENIED",
    )
    assert "DC-HARBORSTONE-APPROVED-VIA-HUMAN" not in _fire(conditions, ctx)


def test_approved_via_human_is_checked_before_the_escalation_condition(conditions):
    ordered = sorted(conditions, key=lambda c: c["priority"])
    ids = [c["condition_id"] for c in ordered]
    assert ids.index("DC-HARBORSTONE-APPROVED-VIA-HUMAN") < ids.index(
        "DC-HARBORSTONE-HUMAN-APPROVAL"
    )
    assert ids.index("DC-HARBORSTONE-AUTHORITY-DENIED") < ids.index(
        "DC-HARBORSTONE-APPROVED-VIA-HUMAN"
    )


def test_screening_conditions_sit_between_authority_denial_and_approval(conditions):
    ordered = sorted(conditions, key=lambda c: c["priority"])
    ids = [c["condition_id"] for c in ordered]
    for screening_id in (
        "DC-HARBORSTONE-SANCTIONS-CONFIRMED",
        "DC-HARBORSTONE-SANCTIONS-REVIEW",
    ):
        assert ids.index("DC-HARBORSTONE-AUTHORITY-DENIED") < ids.index(screening_id)
        assert ids.index(screening_id) < ids.index("DC-HARBORSTONE-APPROVED-VIA-HUMAN")
