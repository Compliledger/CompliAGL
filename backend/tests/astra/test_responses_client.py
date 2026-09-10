"""Responses API parsing + item shaping (no network, no key)."""

from __future__ import annotations

import json

import pytest

from app.astra.errors import AstraNotConfiguredError
from app.astra.responses import client as rc

# A recorded-shape Responses API result with one tool call.
_TOOL_CALL_RESPONSE = {
    "id": "resp_1",
    "output": [
        {
            "type": "function_call",
            "call_id": "call_abc",
            "name": "request_sanctions_screening",
            "arguments": json.dumps(
                {"subject_id": "wallet_002", "subject_type": "wallet", "reason": None}
            ),
        }
    ],
}

_FINAL_MESSAGE_RESPONSE = {
    "id": "resp_2",
    "output": [
        {
            "type": "message",
            "role": "assistant",
            "content": [
                {"type": "output_text", "text": "Screening came back clean; "},
                {"type": "output_text", "text": "no action needed."},
            ],
        }
    ],
}


def test_parse_tool_call():
    parsed = rc.parse_output(_TOOL_CALL_RESPONSE)
    assert parsed.has_tool_calls
    (call,) = parsed.function_calls
    assert call.call_id == "call_abc"
    assert call.name == "request_sanctions_screening"
    assert call.arguments["subject_id"] == "wallet_002"
    assert parsed.text is None


def test_parse_final_message():
    parsed = rc.parse_output(_FINAL_MESSAGE_RESPONSE)
    assert not parsed.has_tool_calls
    assert parsed.text == "Screening came back clean; no action needed."


def test_parse_tolerates_bad_arguments_json():
    parsed = rc.parse_output(
        {"output": [{"type": "function_call", "call_id": "c", "name": "x",
                     "arguments": "{not json"}]}
    )
    assert parsed.function_calls[0].arguments == {}


def test_output_item_helpers_round_trip():
    call = rc.FunctionCall(call_id="c1", name="get_case_data", arguments={"case_id": "X"})
    in_item = rc.function_call_input_item(call)
    assert in_item["type"] == "function_call"
    assert json.loads(in_item["arguments"]) == {"case_id": "X"}

    out_item = rc.function_call_output_item("c1", {"ok": True})
    assert out_item == {
        "type": "function_call_output",
        "call_id": "c1",
        "output": json.dumps({"ok": True}),
    }


def test_create_without_key_raises_not_configured():
    c = rc.AstraResponsesClient(api_key=None)
    assert c.configured is False
    with pytest.raises(AstraNotConfiguredError):
        c.create(instructions="x", input=[], tools=[])


def test_model_defaults_to_gpt_6_astra():
    assert rc.AstraResponsesClient(api_key="sk-test").model == "gpt-6-astra"
