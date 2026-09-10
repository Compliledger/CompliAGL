"""get_case_data / get_authorized_transaction_history compose canonical records
scoped to the session's case."""

from __future__ import annotations

import pytest

from app.astra.context import build_context
from app.astra.errors import ToolValidationError
from app.astra.tools.dispatch import execute_tool_call
from app.db import seed
from app.db.harborstone_package import build_harborstone_package
from app.services.canonical import (
    authority_context_service,
    governance_package_service,
    governed_action_service,
)
from app.services.canonical.authority_context_service import AuthorityContext
from app.services.evidence.connectors import ConnectorRegistry
from app.services.evidence.connectors.harborstone_sentry_screening import (
    harborstone_sentry_screening_connector,
)
from app.utils.canonical_enums import IntentType

ORG = "harborstone-demo"
CASE = "HARBORSTONE-2024-0042"


class _Client:
    def __init__(self, c):
        self._c = c

    def fetch(self, **kw):
        return self._c


@pytest.fixture()
def case_with_history(db_session, monkeypatch):
    seed.seed_organizations(db_session)
    seed.seed_harborstone_actors(db_session)
    pkg = governance_package_service.create(db_session, build_harborstone_package(ORG))
    governance_package_service.validate(db_session, ORG, pkg.id)
    governance_package_service.approve(
        db_session, ORG, pkg.id, approver_principal_id="t", rationale="t"
    )
    governance_package_service.publish(db_session, ORG, pkg.id)
    monkeypatch.setattr(
        authority_context_service, "default_client",
        lambda **kw: _Client(AuthorityContext(
            status="OK", sufficient=True, permission_present=True,
            approval_required=False, findings=("permission_present",),
        )),
    )
    # One APPROVED transfer on the case.
    governed_action_service.propose(
        db_session, ORG,
        actor_id=seed.HARBORSTONE_AIRA_ACTOR_ID,
        intent_type=IntentType.TRANSFER, action="astra_transfer",
        compliidentity_resource="aml.action", compliidentity_action="propose",
        resource_instance=CASE, target_identifier="wallet_001",
        amount_minor=10_000_000, amount_currency="USD",
        extra_parameters={"counterparty": "wallet_001", "direction": "outbound"},
        registry=ConnectorRegistry([harborstone_sentry_screening_connector()]),
    )
    return db_session


def _ctx(db, persona="AIRA"):
    return build_context(db=db, organization_id=ORG, persona_name=persona, case_id=CASE)


def test_get_case_data_composes_sections(case_with_history):
    out = execute_tool_call(
        _ctx(case_with_history), "get_case_data", {"case_id": CASE, "sections": None}
    )
    assert out["case"]["intent_count"] >= 1
    assert out["case"]["latest_policy_resolution_id"]
    # screening evidence surfaced under kyc
    assert "EV-HARBORSTONE-SANCTIONS-SCREENING" in out["kyc"]["evidence_claims"]
    # at least one decision, most-recent-first
    assert out["recent_decisions"]
    assert out["recent_decisions"][0]["outcome"] in {"APPROVED", "DENIED", "ESCALATED"}


def test_get_case_data_section_filter(case_with_history):
    out = execute_tool_call(
        _ctx(case_with_history), "get_case_data", {"case_id": CASE, "sections": ["case"]}
    )
    assert set(out) == {"case_id", "case"}


def test_get_case_data_rejects_other_case(case_with_history):
    with pytest.raises(ToolValidationError):
        execute_tool_call(
            _ctx(case_with_history), "get_case_data",
            {"case_id": "SOME-OTHER-CASE", "sections": None},
        )


def test_transaction_history_returns_only_authorized_approved(case_with_history):
    out = execute_tool_call(
        _ctx(case_with_history), "get_authorized_transaction_history",
        {"case_id": CASE, "limit": 50, "direction": None},
    )
    assert out["count"] == 1
    tx = out["transactions"][0]
    assert tx["decision_outcome"] == "APPROVED"
    assert tx["amount_minor"] == 10_000_000
    assert tx["counterparty"] == "wallet_001"


def test_transaction_history_direction_filter(case_with_history):
    inbound = execute_tool_call(
        _ctx(case_with_history), "get_authorized_transaction_history",
        {"case_id": CASE, "limit": 50, "direction": "inbound"},
    )
    assert inbound["count"] == 0
    outbound = execute_tool_call(
        _ctx(case_with_history), "get_authorized_transaction_history",
        {"case_id": CASE, "limit": 50, "direction": "outbound"},
    )
    assert outbound["count"] == 1


def test_sentry_can_read(case_with_history):
    out = execute_tool_call(
        _ctx(case_with_history, persona="SENTRY"), "get_case_data",
        {"case_id": CASE, "sections": ["kyc"]},
    )
    assert "kyc" in out
