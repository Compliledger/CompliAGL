"""OpenAI Responses API transport for Astra (``gpt-6-astra``).

Only :meth:`AstraResponsesClient.create` touches the network / needs a key.
Everything else here -- building the request, parsing ``response.output`` into
function calls and text, and shaping ``function_call_output`` items -- is pure
and unit-tested against recorded payloads.

Wire shape (Responses API):

* request:  ``model``, ``instructions``, ``input`` (list of items), ``tools``
  (flat function schemas from :func:`app.astra.tools.schemas.tools_for_persona`)
* response: ``output`` is a list; a tool call is an item with
  ``type == "function_call"`` (``call_id`` / ``name`` / ``arguments`` JSON
  string); assistant text is a ``type == "message"`` item whose ``content``
  holds ``type == "output_text"`` parts.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Optional

from app.astra.errors import AstraNotConfiguredError
from app.core.config import settings


@dataclass(frozen=True)
class FunctionCall:
    """One tool call the model asked for."""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class ParsedResponse:
    """The parts of a Responses API result the loop cares about."""

    function_calls: list[FunctionCall] = field(default_factory=list)
    text: Optional[str] = None
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def has_tool_calls(self) -> bool:
        return bool(self.function_calls)


def _as_dict(response: Any) -> dict[str, Any]:
    if isinstance(response, dict):
        return response
    for attr in ("model_dump", "to_dict", "dict"):
        fn = getattr(response, attr, None)
        if callable(fn):
            return fn()
    raise TypeError(f"cannot coerce {type(response)!r} to a response dict")


def parse_output(response: Any) -> ParsedResponse:
    """Extract function calls and assistant text from a Responses API result."""
    data = _as_dict(response)
    parsed = ParsedResponse(raw=data)
    text_parts: list[str] = []

    for item in data.get("output") or []:
        item_type = item.get("type")
        if item_type == "function_call":
            raw_args = item.get("arguments")
            if isinstance(raw_args, str):
                try:
                    args = json.loads(raw_args) if raw_args else {}
                except ValueError:
                    args = {}
            elif isinstance(raw_args, dict):
                args = raw_args
            else:
                args = {}
            parsed.function_calls.append(
                FunctionCall(
                    call_id=item.get("call_id") or item.get("id") or "",
                    name=item.get("name") or "",
                    arguments=args,
                )
            )
        elif item_type == "message":
            for part in item.get("content") or []:
                if part.get("type") in ("output_text", "text"):
                    text_parts.append(part.get("text") or "")

    if text_parts:
        parsed.text = "".join(text_parts)
    return parsed


def function_call_input_item(call: FunctionCall) -> dict[str, Any]:
    """Re-materialize a model function call as an ``input`` item for the next turn."""
    return {
        "type": "function_call",
        "call_id": call.call_id,
        "name": call.name,
        "arguments": json.dumps(call.arguments),
    }


def function_call_output_item(
    call_id: str, output: dict[str, Any]
) -> dict[str, Any]:
    """Shape a tool result as a ``function_call_output`` ``input`` item."""
    return {
        "type": "function_call_output",
        "call_id": call_id,
        "output": json.dumps(output, default=str),
    }


def user_message_item(text: str) -> dict[str, Any]:
    return {
        "type": "message",
        "role": "user",
        "content": [{"type": "input_text", "text": text}],
    }


class AstraResponsesClient:
    """Thin wrapper over ``openai.OpenAI().responses.create``.

    Construction never fails; :meth:`create` raises
    :class:`~app.astra.errors.AstraNotConfiguredError` when no API key is
    configured, so the rest of the layer stays usable without one.
    """

    def __init__(
        self,
        *,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ) -> None:
        self._api_key = api_key or getattr(settings, "OPENAI_API_KEY", None)
        self.model = model or getattr(settings, "ASTRA_MODEL", "gpt-6-astra")

    @property
    def configured(self) -> bool:
        return bool(self._api_key)

    def create(
        self,
        *,
        instructions: str,
        input: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ParsedResponse:
        """Call the Responses API and return the parsed result."""
        if not self._api_key:
            raise AstraNotConfiguredError(
                "OPENAI_API_KEY is not set -- the Astra Responses API transport "
                "is not available yet. Tool schemas and dispatch work without "
                "it."
            )
        try:  # pragma: no cover - exercised only once the key is present
            import openai
        except ImportError as exc:  # pragma: no cover
            raise AstraNotConfiguredError(
                "the 'openai' package is not installed"
            ) from exc

        client = openai.OpenAI(api_key=self._api_key)
        response = client.responses.create(  # pragma: no cover - network
            model=self.model,
            instructions=instructions,
            input=input,
            tools=tools,
        )
        return parse_output(response)
