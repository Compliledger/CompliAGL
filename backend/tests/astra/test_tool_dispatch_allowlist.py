"""Dispatch is forbidden-deny, then default-deny -- before any handler runs."""

from __future__ import annotations

import pytest

from app.astra.context import build_context
from app.astra.errors import ForbiddenToolError, ToolValidationError
from app.astra.tools import handlers
from app.astra.tools.dispatch import execute_tool_call

ORG = "harborstone-demo"
CASE = "HARBORSTONE-2024-0042"


def _ctx(persona_name):
    # db is unused for the checks under test (they fail before any handler runs).
    return build_context(
        db=None, organization_id=ORG, persona_name=persona_name, case_id=CASE
    )


@pytest.mark.parametrize(
    "forbidden",
    ["transfer_funds", "freeze_account", "restrict_account", "execute_contract"],
)
def test_forbidden_execution_tools_are_refused_for_every_persona(forbidden):
    for persona_name in ("AIRA", "SENTRY"):
        with pytest.raises(ForbiddenToolError) as exc:
            execute_tool_call(_ctx(persona_name), forbidden, {})
        assert exc.value.tool_name == forbidden


def test_unknown_tool_is_refused():
    with pytest.raises(ForbiddenToolError):
        execute_tool_call(_ctx("AIRA"), "list_all_cases", {})


def test_sentry_cannot_propose_or_screen():
    for tool in ("propose_governed_action", "request_sanctions_screening"):
        with pytest.raises(ForbiddenToolError) as exc:
            execute_tool_call(_ctx("SENTRY"), tool, {})
        assert "SENTRY tool allow-list" in exc.value.reason


def test_handler_is_not_reached_when_denied(monkeypatch):
    called = {"n": 0}

    def _boom(*a, **k):
        called["n"] += 1
        raise AssertionError("handler must not run for a denied call")

    monkeypatch.setattr(handlers, "propose_governed_action", _boom)
    # dispatch resolves the handler from its own registry at import time, so
    # patch there too:
    from app.astra.tools import dispatch as _dispatch

    monkeypatch.setitem(_dispatch.TOOL_HANDLERS, "propose_governed_action", _boom)

    with pytest.raises(ForbiddenToolError):
        execute_tool_call(_ctx("SENTRY"), "propose_governed_action", {})
    assert called["n"] == 0


def test_allowed_tool_with_bad_arguments_raises_validation_not_forbidden():
    # 'limit' out of range for get_authorized_transaction_history.
    with pytest.raises(ToolValidationError):
        execute_tool_call(
            _ctx("AIRA"),
            "get_authorized_transaction_history",
            {"case_id": CASE, "limit": 9999, "direction": None},
        )
