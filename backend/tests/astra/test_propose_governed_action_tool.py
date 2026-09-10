"""propose_governed_action: terminal, scope-locked, never auto-executes."""

from __future__ import annotations

import pytest

from app.astra.context import build_context
from app.astra.errors import ToolValidationError
from app.astra.tools.dispatch import execute_tool_call
from app.db import seed
from app.db.harborstone_package import build_harborstone_package
from app.repositories.canonical import ExecutionAuthorizationRepository
from app.services.canonical import authority_context_service, governance_package_service
from app.services.canonical.authority_context_service import AuthorityContext

ORG = "harborstone-demo"
CASE = "HARBORSTONE-2024-0042"


class _Client:
    def __init__(self, ctx):
        self._ctx = ctx

    def fetch(self, **kwargs):
        return self._ctx


@pytest.fixture()
def ctx(db_session, monkeypatch):
    seed.seed_organizations(db_session)
    seed.seed_harborstone_actors(db_session)
    pkg = governance_package_service.create(db_session, build_harborstone_package(ORG))
    governance_package_service.validate(db_session, ORG, pkg.id)
    governance_package_service.approve(
        db_session, ORG, pkg.id, approver_principal_id="t", rationale="t"
    )
    governance_package_service.publish(db_session, ORG, pkg.id)
    monkeypatch.setattr(
        authority_context_service,
        "default_client",
        lambda **kw: _Client(
            AuthorityContext(
                status="OK", sufficient=True, permission_present=True,
                approval_required=False, findings=("permission_present",),
            )
        ),
    )
    return build_context(
        db=db_session, organization_id=ORG, persona_name="AIRA", case_id=CASE
    )


def _args(**over):
    base = {
        "action_type": "transfer",
        "compliidentity_resource": "aml.action",
        "compliidentity_action": "propose",
        "resource_instance": CASE,
        "target_identifier": "wallet_001",
        "rationale": "reviewed and clear",
        "amount_minor": 24_999_999,
        "amount_currency": "USD",
        "parameters": None,
    }
    base.update(over)
    return base


def test_clean_proposal_is_approved_and_terminal_without_executing(ctx):
    out = execute_tool_call(ctx, "propose_governed_action", _args())
    assert out["terminal"] is True
    assert out["outcome"] == "APPROVED"
    assert "authorization_issuable" in out["next_step"]
    # No ExecutionAuthorization was issued by the tool.
    assert not ExecutionAuthorizationRepository(ctx.db).list_for_intent(
        ORG, out["intent_id"]
    )


def test_confirmed_match_is_denied(ctx):
    out = execute_tool_call(
        ctx, "propose_governed_action", _args(target_identifier="wallet_003")
    )
    assert out["outcome"] == "DENIED"
    assert out["next_step"].startswith("blocked")


def test_out_of_scope_case_is_refused(ctx):
    with pytest.raises(ToolValidationError):
        execute_tool_call(
            ctx, "propose_governed_action", _args(resource_instance="OTHER-CASE-9999")
        )


def test_model_cannot_request_the_approve_verb(ctx):
    with pytest.raises(ToolValidationError):
        execute_tool_call(
            ctx, "propose_governed_action", _args(compliidentity_action="approve")
        )


def test_amount_without_currency_is_refused(ctx):
    with pytest.raises(ToolValidationError):
        execute_tool_call(
            ctx,
            "propose_governed_action",
            _args(amount_minor=1000, amount_currency=None),
        )


def test_bounded_parameters_and_counterparty_land_on_the_intent(ctx):
    import json

    from app.repositories.canonical import IntentRepository

    out = execute_tool_call(
        ctx,
        "propose_governed_action",
        _args(parameters={"direction": "outbound", "note": "vendor payout"}),
    )
    params = json.loads(
        IntentRepository(ctx.db).get(ORG, out["intent_id"]).parameters
    )
    assert params["direction"] == "outbound"
    assert params["note"] == "vendor payout"
    assert params["counterparty"] == "wallet_001"  # derived from target_identifier


def test_parameters_rejects_unknown_keys(ctx):
    with pytest.raises(ToolValidationError):
        execute_tool_call(
            ctx,
            "propose_governed_action",
            _args(parameters={"direction": None, "note": None, "evil": "x"}),
        )
