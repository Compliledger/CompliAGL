"""Typed failures for the Astra tool-calling layer."""

from __future__ import annotations


class AstraError(Exception):
    """Base class for every Astra-layer failure."""


class AstraNotConfiguredError(AstraError):
    """The Responses API transport was invoked without an API key / while disabled.

    Raised by :mod:`app.astra.responses.client` and
    :func:`app.astra.responses.loop.run_agent_turn`. Everything that does not
    touch the network (schemas, dispatch, handlers) works without a key.
    """


class ForbiddenToolError(AstraError):
    """A tool call was refused before any handler ran.

    Three cases, all fail-closed:

    * the name is on :data:`app.astra.tools.dispatch.FORBIDDEN_TOOL_NAMES`
      (an execution tool the model must never get),
    * the name is not in the calling persona's ``allowed_tools`` (default-deny),
    * the name has no registered handler.
    """

    def __init__(self, tool_name: str, reason: str) -> None:
        self.tool_name = tool_name
        self.reason = reason
        super().__init__(f"tool {tool_name!r} refused: {reason}")


class ToolValidationError(AstraError):
    """The model's tool-call arguments failed schema or scope validation."""

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        super().__init__(f"{tool_name}: {message}")
