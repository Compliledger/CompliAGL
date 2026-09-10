"""The Astra agentic loop.

``run_agent_turn`` drives one user turn: send the input + persona tools to the
model, run every tool call it makes through ``tools.dispatch.execute_tool_call``,
feed the results back, and repeat -- stopping when the model returns a final
message, when it calls ``propose_governed_action`` (terminal), or when the tool
iteration cap is hit.

Refusals from dispatch (``ForbiddenToolError`` / ``ToolValidationError``) are
turned into a structured tool-error result the model sees on the next turn --
they never abort the loop, and they never let the tool run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.astra.context import AstraInvocationContext
from app.astra.errors import (
    AstraNotConfiguredError,
    ForbiddenToolError,
    ToolValidationError,
)
from app.astra.personas import TOOL_PROPOSE_GOVERNED_ACTION
from app.astra.responses.client import (
    AstraResponsesClient,
    ParsedResponse,
    function_call_input_item,
    function_call_output_item,
    user_message_item,
)
from app.astra.tools.dispatch import execute_tool_call
from app.astra.tools.schemas import tools_for_persona
from app.core.config import settings


@dataclass
class ToolInvocation:
    tool: str
    arguments: dict[str, Any]
    output: dict[str, Any]
    error: Optional[str] = None


@dataclass
class AgentTurnResult:
    stopped: str  # "final_message" | "proposed_governed_action" | "max_iterations"
    final_text: Optional[str] = None
    decision: Optional[dict[str, Any]] = None
    invocations: list[ToolInvocation] = field(default_factory=list)
    iterations: int = 0


def run_agent_turn(
    ctx: AstraInvocationContext,
    *,
    user_message: str,
    client: Optional[AstraResponsesClient] = None,
    max_iterations: Optional[int] = None,
) -> AgentTurnResult:
    """Run one user turn for ``ctx.persona`` against the Responses API."""
    if not getattr(settings, "ASTRA_ENABLED", False):
        raise AstraNotConfiguredError(
            "ASTRA_ENABLED is false -- the agent loop is disabled."
        )
    client = client or AstraResponsesClient()
    cap = int(max_iterations or getattr(settings, "ASTRA_MAX_TOOL_ITERATIONS", 8))
    tools = tools_for_persona(ctx.persona)

    input_items: list[dict[str, Any]] = [user_message_item(user_message)]
    result = AgentTurnResult(stopped="max_iterations")

    for iteration in range(1, cap + 1):
        result.iterations = iteration
        parsed: ParsedResponse = client.create(
            instructions=ctx.persona.system_prompt,
            input=input_items,
            tools=tools,
        )

        if not parsed.has_tool_calls:
            result.stopped = "final_message"
            result.final_text = parsed.text
            return result

        terminal_decision: Optional[dict[str, Any]] = None
        for call in parsed.function_calls:
            input_items.append(function_call_input_item(call))
            error: Optional[str] = None
            try:
                output = execute_tool_call(ctx, call.name, call.arguments)
            except (ForbiddenToolError, ToolValidationError) as exc:
                error = str(exc)
                output = {
                    "error": type(exc).__name__,
                    "detail": str(exc),
                }
            input_items.append(
                function_call_output_item(call.call_id, output)
            )
            result.invocations.append(
                ToolInvocation(
                    tool=call.name,
                    arguments=call.arguments,
                    output=output,
                    error=error,
                )
            )
            if call.name == TOOL_PROPOSE_GOVERNED_ACTION and error is None:
                terminal_decision = output

        if terminal_decision is not None:
            result.stopped = "proposed_governed_action"
            result.decision = terminal_decision
            return result

    return result
