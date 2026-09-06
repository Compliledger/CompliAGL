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
    build_harborstone_package,
)
from app.services.canonical.package_interpreter import evaluate_expression


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


def test_package_opts_into_authority_context():
    package = build_harborstone_package("harborstone-demo")
    assert package.requires_authority_context is True


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
