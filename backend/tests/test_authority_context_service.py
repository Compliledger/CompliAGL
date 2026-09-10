"""Parse-level tests for the CompliIdentity authority-context client.

Every fixture body here is a trimmed-but-faithful copy of a **real** response
captured from a live CompliIdentity instance during that repo's demo3
acceptance run (``demo3_results.json``, 13 authority-context calls). Until
this file existed, nothing exercised ``_parse_ok`` against a real response
shape -- the three mismatches it now covers (``findings`` vs a nonexistent
``reason`` key, ``current_trust_state`` as an object not a string, and the
``integrity`` proof block) all shipped undetected because the only other
authority tests construct ``AuthorityContext`` directly via a fake client.

``PROPOSE_AT_THRESHOLD.applicable_approvals`` is likewise verbatim, from the
demo3 step-2 capture (``demo3_step2/compliagl_scenarios_results.json``,
scenario 4b).

See ``docs/COMPLIIDENTITY_CONTRACT_VOCABULARY_CONFIRMED.md`` for the full
confirmed finding vocabulary.
"""

from __future__ import annotations

import json

import httpx
import pytest

from app.services.canonical import decision_service
from app.services.canonical.authority_context_service import (
    AuthorityContextClient,
    _derive_reason,
    _parse_ok,
)

# --------------------------------------------------------------------------- #
# Real captured response bodies (trimmed to the fields _parse_ok reads plus a
# few neighbours for realism). Every one is status 200.
# --------------------------------------------------------------------------- #
_TRUST_STATE_ABSENT = {
    "present": False,
    "fail_closed": True,
    "stale": False,
    "refresh_required": True,
    "decision_id": None,
    "outcome": None,
    "valid_until": None,
    "policy_id": None,
    "policy_version": None,
    "reason_codes": ["trust_state_absent"],
}
_INTEGRITY = {
    "content_hash": "17cfec6fb0535896e20bc445372cd60b0395707bd2e49484be5bdb46f30f06d1",
    "signature": "dd943d5de21323921fef5ef4633ee50f7dce09daac73e40a9c7b731f8d65e5391",
    "signature_algorithm": "ed25519",
    "signer_key_id": "compliidentity.proof.ed25519.dev",
}


def _body(*, afr: dict, active: bool = True) -> dict:
    return {
        "contract_id": "compliidentity.agl.authority.v1",
        "contract_version": "1",
        "tenant_id": "harborstone-demo",
        "principal_id": "714582cf-1405-47af-beef-c6bf8b6106f3",
        "active": active,
        "authorizes": False,
        "executes": False,
        "agl_decision": "not_made",
        "authority_revision": "21fd1eb8d0cbe991d48fddf095cf9f453b828613883d083f42cefeb90f1a96bf",
        "proof_ref": None,
        "current_trust_state": dict(_TRUST_STATE_ABSENT),
        "integrity": dict(_INTEGRITY),
        "authority_for_request": afr,
        "error": None,
    }


# AC1 -- AIRA aml.case:read, in scope: fully authorized happy path.
AC1_IN_SCOPE_READ = _body(
    afr={
        "sufficient": True,
        "permission_present": True,
        "limit_exceeded": False,
        "approval_required": False,
        "findings": ["permission_present", "trust_absent", "trust_refresh_required"],
    }
)

# AIRA propose amount == $250,000.00: approval_required both as bool and finding.
# applicable_approvals is verbatim from the demo3 step-2 capture (scenario 4b,
# demo3_step2/compliagl_scenarios_results.json) -- CompliIdentity's own
# declaration that a propose over the threshold must be approved by a HUMAN.
PROPOSE_AT_THRESHOLD = _body(
    afr={
        "sufficient": False,
        "permission_present": True,
        "limit_exceeded": False,
        "approval_required": True,
        "findings": [
            "permission_present",
            "approval_required",
            "trust_absent",
            "trust_refresh_required",
        ],
        "applicable_approvals": [
            {
                "resource": "aml.action",
                "action": "propose",
                "attribute": "amount",
                "threshold": "24999999",
                "approver_principal_type": "HUMAN",
                "unit": None,
                "source": "role_permission:2a8e4a7c-ccc6-43c9-aa4e-d0905ab69527:v1",
            }
        ],
        "applicable_limits": [],
    }
)

# AC5 -- SENTRY aml.case:read outside its delegated scope.
OUT_OF_SCOPE = _body(
    afr={
        "sufficient": False,
        "permission_present": False,
        "limit_exceeded": False,
        "approval_required": False,
        "findings": ["permission_missing", "trust_absent", "trust_refresh_required"],
    }
)

# bonus -- SENTRY sanctions.screening:read on the wrong case instance:
# permission is present, but the resource_instance is not in the grant scope.
RESOURCE_SCOPE_UNMATCHED = _body(
    afr={
        "sufficient": False,
        "permission_present": True,
        "limit_exceeded": False,
        "approval_required": False,
        "findings": [
            "permission_present",
            "resource_scope_unmatched",
            "trust_absent",
            "trust_refresh_required",
        ],
    }
)

# G1 -- AIRA after being disabled.
PRINCIPAL_NOT_ACTIVE = _body(
    active=False,
    afr={
        "sufficient": False,
        "permission_present": False,
        "limit_exceeded": False,
        "approval_required": False,
        "findings": [
            "principal_not_active",
            "trust_absent",
            "trust_refresh_required",
        ],
    },
)

# H1 -- SENTRY after the AIRA->SENTRY delegation was explicitly revoked:
# delegation_revoked co-occurs with permission_missing.
DELEGATION_REVOKED = _body(
    afr={
        "sufficient": False,
        "permission_present": False,
        "limit_exceeded": False,
        "approval_required": False,
        "findings": [
            "permission_missing",
            "delegation_revoked",
            "trust_absent",
            "trust_refresh_required",
        ],
    }
)


# --------------------------------------------------------------------------- #
# _parse_ok against the real shapes
# --------------------------------------------------------------------------- #
def test_happy_path_derives_no_reason_and_keeps_raw_findings():
    ctx = _parse_ok(AC1_IN_SCOPE_READ)
    assert ctx.status == "OK"
    # The bug this replaces: authority_for_request has no "reason" key, so the
    # old code produced reason=None on every call. Here None is *correct* --
    # nothing actionable was reported -- but for the right reason now.
    assert ctx.reason is None
    assert ctx.sufficient is True
    assert ctx.permission_present is True
    assert ctx.approval_required is False
    assert ctx.limit_exceeded is False
    # Informational findings survive verbatim for conditions that want them,
    # but never leak into the derived reason.
    assert ctx.findings == (
        "permission_present",
        "trust_absent",
        "trust_refresh_required",
    )


def test_current_trust_state_parsed_as_object_not_string():
    ctx = _parse_ok(AC1_IN_SCOPE_READ)
    assert isinstance(ctx.current_trust_state, dict)
    assert ctx.current_trust_state["fail_closed"] is True
    assert ctx.current_trust_state["reason_codes"] == ["trust_state_absent"]


def test_integrity_content_hash_captured():
    ctx = _parse_ok(AC1_IN_SCOPE_READ)
    assert ctx.integrity_content_hash == _INTEGRITY["content_hash"]
    # proof_ref is null on every real response -- integrity is the anchor.
    assert ctx.raw["proof_ref"] is None


def test_approval_required_derives_escalation_reason():
    ctx = _parse_ok(PROPOSE_AT_THRESHOLD)
    assert ctx.reason == "approval_required"
    assert ctx.approval_required is True
    assert ctx.sufficient is False


def test_applicable_approvals_parsed_from_real_body():
    ctx = _parse_ok(PROPOSE_AT_THRESHOLD)
    assert len(ctx.applicable_approvals) == 1
    entry = ctx.applicable_approvals[0]
    assert entry["action"] == "propose"
    assert entry["approver_principal_type"] == "HUMAN"
    assert entry["threshold"] == "24999999"


def test_required_approver_types_distilled_from_real_body():
    """decision_service persists Decision.required_approver_types straight from
    this parsed value -- the persisted field traces to CompliIdentity's real
    applicable_approvals[].approver_principal_type, not a synthetic constant."""
    ctx = _parse_ok(PROPOSE_AT_THRESHOLD)
    assert decision_service._required_approver_types(ctx, "propose") == ["HUMAN"]
    # Scoped to the probed action: nothing is claimed for a different action.
    assert decision_service._required_approver_types(ctx, "approve") == []
    assert decision_service._required_approver_types(None, "propose") == []


def test_permission_missing_derives_denial_reason():
    ctx = _parse_ok(OUT_OF_SCOPE)
    assert ctx.reason == "permission_missing"
    assert ctx.sufficient is False


def test_resource_scope_unmatched_derives_denial_reason():
    ctx = _parse_ok(RESOURCE_SCOPE_UNMATCHED)
    # permission_present is True here -- the denial is purely the instance
    # scope narrowing, which the design doc did not originally anticipate.
    assert ctx.permission_present is True
    assert ctx.reason == "resource_scope_unmatched"


def test_principal_not_active_derives_denial_reason():
    ctx = _parse_ok(PRINCIPAL_NOT_ACTIVE)
    assert ctx.active is False
    assert ctx.reason == "principal_not_active"


def test_delegation_revoked_wins_over_co_present_permission_missing():
    ctx = _parse_ok(DELEGATION_REVOKED)
    # Both findings are DENIED-worthy; the more specific one is reported.
    assert set(("permission_missing", "delegation_revoked")).issubset(ctx.findings)
    assert ctx.reason == "delegation_revoked"


def test_malformed_trust_state_normalizes_to_none():
    body = _body(afr=AC1_IN_SCOPE_READ["authority_for_request"])
    body["current_trust_state"] = "present"  # legacy/garbage string shape
    ctx = _parse_ok(body)
    assert ctx.current_trust_state is None


# --------------------------------------------------------------------------- #
# _derive_reason unit coverage of the priority rules
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "afr, expected",
    [
        ({"findings": []}, None),
        ({"findings": ["permission_present", "trust_absent"]}, None),
        ({"findings": ["approval_required"]}, "approval_required"),
        ({"approval_required": True, "findings": []}, "approval_required"),
        ({"limit_exceeded": True, "findings": []}, "limit_exceeded"),
        ({"findings": ["permission_missing"]}, "permission_missing"),
        (
            # a hard denial is never masked into an escalation
            {"approval_required": True, "findings": ["permission_missing"]},
            "permission_missing",
        ),
        (
            {"findings": ["resource_scope_unmatched", "permission_missing"]},
            "resource_scope_unmatched",
        ),
        (
            {"findings": ["permission_missing", "principal_not_active"]},
            "principal_not_active",
        ),
        (
            # limit_exceeded outranks approval_required, but not a finding denial
            {"limit_exceeded": True, "approval_required": True, "findings": []},
            "limit_exceeded",
        ),
    ],
)
def test_derive_reason_priority(afr, expected):
    assert _derive_reason(afr) == expected


# --------------------------------------------------------------------------- #
# fetch() end-to-end against a real body via a mock transport
# --------------------------------------------------------------------------- #
def test_fetch_parses_real_body_over_transport():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["headers"] = request.headers
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=OUT_OF_SCOPE)

    client = AuthorityContextClient(
        base_url="http://compliidentity.test",
        service_principal_id="0812c9a2-f1c2-4cd2-81a8-8384502ad77e",
        http_client=httpx.Client(
            base_url="http://compliidentity.test",
            transport=httpx.MockTransport(handler),
        ),
    )
    ctx = client.fetch(
        organization_id="harborstone-demo",
        principal_id="640372b2-e781-42de-a810-72942fb154f0",
        resource="aml.case",
        action="read",
        resource_instance="HARBORSTONE-2024-0042",
    )

    assert ctx.status == "OK"
    assert ctx.reason == "permission_missing"
    assert ctx.sufficient is False
    assert seen["url"].endswith(
        "/api/v1/tenants/harborstone-demo/authority-context/"
        "640372b2-e781-42de-a810-72942fb154f0"
    )
    assert seen["headers"]["X-Tenant-Id"] == "harborstone-demo"
    assert seen["headers"]["X-Actor-Principal-Id"] == (
        "0812c9a2-f1c2-4cd2-81a8-8384502ad77e"
    )
    assert seen["body"]["resource"] == "aml.case"
    assert seen["body"]["action"] == "read"
    assert seen["body"]["resource_instance"] == "HARBORSTONE-2024-0042"
