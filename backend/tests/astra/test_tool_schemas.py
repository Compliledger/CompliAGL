"""The tool-schema surface is exactly the four read/propose tools -- no more."""

from __future__ import annotations

import jsonschema
import pytest

from app.astra import personas
from app.astra.tools import schemas
from app.astra.tools.dispatch import FORBIDDEN_TOOL_NAMES, TOOL_HANDLERS

_EXPECTED = {
    "get_case_data",
    "get_authorized_transaction_history",
    "request_sanctions_screening",
    "propose_governed_action",
}


def test_schema_registry_is_exactly_the_four_tools():
    assert set(schemas.SCHEMAS_BY_NAME) == _EXPECTED
    assert set(TOOL_HANDLERS) == _EXPECTED


def test_no_forbidden_tool_has_a_schema_or_handler():
    assert FORBIDDEN_TOOL_NAMES == {
        "transfer_funds",
        "freeze_account",
        "restrict_account",
        "execute_contract",
    }
    assert FORBIDDEN_TOOL_NAMES.isdisjoint(schemas.SCHEMAS_BY_NAME)
    assert FORBIDDEN_TOOL_NAMES.isdisjoint(TOOL_HANDLERS)


def test_no_persona_allow_list_contains_a_forbidden_tool():
    for name in personas.persona_names():
        persona = personas.get_persona(name)
        assert FORBIDDEN_TOOL_NAMES.isdisjoint(persona.allowed_tools)
        assert set(persona.allowed_tools) <= _EXPECTED


def test_aira_gets_all_four_sentry_is_read_only():
    aira = personas.get_persona("AIRA")
    sentry = personas.get_persona("SENTRY")
    assert set(aira.allowed_tools) == _EXPECTED
    assert set(sentry.allowed_tools) == {
        "get_case_data",
        "get_authorized_transaction_history",
    }
    # Hard boundary: SENTRY must not be able to propose.
    assert "propose_governed_action" not in sentry.allowed_tools
    assert "request_sanctions_screening" not in sentry.allowed_tools


def _assert_strict_object(node: dict) -> None:
    """Every object node (nested included) must be closed and fully-required."""
    node_type = node.get("type")
    types = node_type if isinstance(node_type, list) else [node_type]
    if "object" in types:
        assert node.get("additionalProperties") is False, node
        assert set(node.get("required", [])) == set(node.get("properties", {})), node
        for child in node.get("properties", {}).values():
            _assert_strict_object(child)
    if "array" in types and isinstance(node.get("items"), dict):
        _assert_strict_object(node["items"])


@pytest.mark.parametrize("name", sorted(_EXPECTED))
def test_every_schema_is_valid_json_schema_and_strict_shaped(name):
    schema = schemas.SCHEMAS_BY_NAME[name]
    assert schema["type"] == "function"
    assert schema["name"] == name
    assert schema["strict"] is True
    params = schema["parameters"]
    assert params["type"] == "object"
    jsonschema.Draft202012Validator.check_schema(params)
    # strict mode: every object (nested too) is closed + every property required.
    _assert_strict_object(params)


def test_tools_for_persona_is_a_subset_of_the_allow_list():
    for name in personas.persona_names():
        persona = personas.get_persona(name)
        served = {t["name"] for t in schemas.tools_for_persona(persona)}
        assert served == set(persona.allowed_tools)
