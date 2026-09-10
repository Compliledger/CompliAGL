"""The agentic loop: tool round-trips, terminal propose, refusals, iteration cap.

Uses a scripted fake client -- no network. The tool side is real (dispatch +
handlers + the canonical pipeline).
"""

from __future__ import annotations

import pytest

from app.astra.context import build_context
from app.astra.responses.client import FunctionCall, ParsedResponse
from app.astra.responses.loop import run_agent_turn
from app.db import seed
from app.db.harborstone_package import build_harborstone_package
from app.services.canonical import authority_context_service, governance_package_service
from app.services.canonical.authority_context_service import AuthorityContext

ORG = "harborstone-demo"
CASE = "HARBORSTONE-2024-0042"


class _ScriptedClient:
    """Returns pre-built ParsedResponses, one per create() call."""

    def __init__(self, *responses: ParsedResponse) -> None:
        self._responses = list(responses)
        self.calls: list[dict] = []

    def create(self, *, instructions, input, tools):
        self.calls.append({"instructions": instructions, "input": list(input), "tools": tools})
        if not self._responses:
            raise AssertionError("scripted client ran out of responses")
        return self._responses.pop(0)


def _fc(name, args, call_id="c"):
    return ParsedResponse(function_calls=[FunctionCall(call_id=call_id, name=name, arguments=args)])


def _text(t):
    return ParsedResponse(text=t)


class _Client:
    def __init__(self, ctx):
        self._ctx = ctx

    def fetch(self, **kwargs):
        return self._ctx


@pytest.fixture(autouse=True)
def _enable_astra(monkeypatch):
    from app.core import config

    monkeypatch.setattr(config.settings, "ASTRA_ENABLED", True, raising=False)


@pytest.fixture()
def harborstone(db_session, monkeypatch):
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
    return db_session


def _ctx(db, persona="AIRA"):
    return build_context(db=db, organization_id=ORG, persona_name=persona, case_id=CASE)


def test_disabled_loop_refuses(db_session, monkeypatch):
    from app.core import config
    from app.astra.errors import AstraNotConfiguredError

    monkeypatch.setattr(config.settings, "ASTRA_ENABLED", False, raising=False)
    with pytest.raises(AstraNotConfiguredError):
        run_agent_turn(_ctx(db_session), user_message="hi", client=_ScriptedClient())


def test_read_tool_then_final_message(harborstone):
    client = _ScriptedClient(
        _fc("get_case_data", {"case_id": CASE, "sections": None}),
        _text("No prior decisions on this case."),
    )
    result = run_agent_turn(_ctx(harborstone), user_message="summarise the case", client=client)
    assert result.stopped == "final_message"
    assert result.final_text == "No prior decisions on this case."
    assert [i.tool for i in result.invocations] == ["get_case_data"]
    assert result.invocations[0].error is None


def test_propose_is_terminal(harborstone):
    client = _ScriptedClient(
        _fc("propose_governed_action", {
            "action_type": "transfer",
            "compliidentity_resource": "aml.action",
            "compliidentity_action": "propose",
            "resource_instance": CASE,
            "target_identifier": "wallet_001",
            "rationale": "clear",
            "amount_minor": 24_999_999,
            "amount_currency": "USD",
            "parameters": None,
        }),
        _text("this should never be reached"),
    )
    result = run_agent_turn(_ctx(harborstone), user_message="proceed", client=client)
    assert result.stopped == "proposed_governed_action"
    assert result.decision["outcome"] == "APPROVED"
    # The loop stopped -- the second scripted response was not consumed.
    assert len(client.calls) == 1


def test_forbidden_tool_call_is_refused_but_loop_continues(harborstone):
    client = _ScriptedClient(
        _fc("transfer_funds", {"to": "wallet_x", "amount": 999}),
        _text("Understood, I cannot do that directly."),
    )
    result = run_agent_turn(_ctx(harborstone), user_message="just send it", client=client)
    assert result.stopped == "final_message"
    (inv,) = result.invocations
    assert inv.tool == "transfer_funds"
    assert inv.error is not None
    assert inv.output["error"] == "ForbiddenToolError"


def test_sentry_cannot_propose_via_the_loop(harborstone):
    client = _ScriptedClient(
        _fc("propose_governed_action", {
            "action_type": "transfer", "compliidentity_resource": "aml.action",
            "compliidentity_action": "propose", "resource_instance": CASE,
            "target_identifier": "wallet_001", "rationale": "x",
            "amount_minor": None, "amount_currency": None, "parameters": None,
        }),
        _text("I don't have that capability."),
    )
    result = run_agent_turn(_ctx(harborstone, persona="SENTRY"), user_message="act", client=client)
    assert result.stopped == "final_message"
    assert result.invocations[0].error is not None
    assert result.decision is None


def test_iteration_cap(harborstone):
    client = _ScriptedClient(*[
        _fc("get_case_data", {"case_id": CASE, "sections": ["case"]}, call_id=f"c{i}")
        for i in range(10)
    ])
    result = run_agent_turn(
        _ctx(harborstone), user_message="loop", client=client, max_iterations=3
    )
    assert result.stopped == "max_iterations"
    assert result.iterations == 3
    assert len(result.invocations) == 3
