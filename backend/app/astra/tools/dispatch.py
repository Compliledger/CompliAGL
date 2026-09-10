"""Tool-call dispatch -- forbidden-deny, then default-deny, then validate, then run.

``execute_tool_call`` is the single entry point the agent loop uses to run a
model-requested tool. Nothing else should call handlers directly.

Order of checks (all fail-closed, before any handler side effect):

1. **Forbidden.** The name is on :data:`FORBIDDEN_TOOL_NAMES` -- an execution
   tool the model must never be able to invoke. There is no handler for these
   and there never will be.
2. **Default-deny.** The name is not in the calling persona's ``allowed_tools``.
3. **No handler.** The name has no registered handler.
4. **Schema.** The arguments do not validate against the tool's JSON schema.

Only then is the persona-scoped handler called with ``ctx`` injected first.
"""

from __future__ import annotations

from typing import Any, Callable

import jsonschema

from app.astra.context import AstraInvocationContext
from app.astra.errors import ForbiddenToolError, ToolValidationError
from app.astra.tools import handlers as _handlers
from app.astra.tools.schemas import SCHEMAS_BY_NAME

# Execution tools the model must never receive. Kept as an explicit denylist in
# addition to the (default-deny) persona allow-lists: defense in depth, and a
# single greppable statement of the boundary.
FORBIDDEN_TOOL_NAMES: frozenset[str] = frozenset(
    {
        "transfer_funds",
        "freeze_account",
        "restrict_account",
        "execute_contract",
    }
)

TOOL_HANDLERS: dict[str, Callable[..., dict[str, Any]]] = {
    "get_case_data": _handlers.get_case_data,
    "get_authorized_transaction_history": _handlers.get_authorized_transaction_history,
    "request_sanctions_screening": _handlers.request_sanctions_screening,
    "propose_governed_action": _handlers.propose_governed_action,
}

# Structural invariant: no handler is ever registered for a forbidden name.
assert FORBIDDEN_TOOL_NAMES.isdisjoint(TOOL_HANDLERS), (
    "a forbidden tool name has a registered handler"
)
assert set(TOOL_HANDLERS) == set(SCHEMAS_BY_NAME), (
    "handler registry and schema registry disagree"
)


def _validate_arguments(tool_name: str, arguments: dict[str, Any]) -> None:
    schema = SCHEMAS_BY_NAME[tool_name]["parameters"]
    try:
        jsonschema.validate(instance=arguments, schema=schema)
    except jsonschema.ValidationError as exc:
        raise ToolValidationError(
            tool_name, f"arguments failed schema validation: {exc.message}"
        ) from exc


def execute_tool_call(
    ctx: AstraInvocationContext,
    tool_name: str,
    arguments: dict[str, Any] | None,
) -> dict[str, Any]:
    """Run one model-requested tool call for ``ctx.persona``. See module docstring."""
    if tool_name in FORBIDDEN_TOOL_NAMES:
        raise ForbiddenToolError(
            tool_name,
            "execution tools are never exposed to the model; the application "
            "executes actions, and only after a governance decision",
        )
    if tool_name not in ctx.persona.allowed_tools:
        raise ForbiddenToolError(
            tool_name,
            f"not in the {ctx.persona.name} tool allow-list "
            f"{list(ctx.persona.allowed_tools)}",
        )
    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        raise ForbiddenToolError(tool_name, "no registered handler")

    args = dict(arguments or {})
    _validate_arguments(tool_name, args)
    return handler(ctx, **args)
