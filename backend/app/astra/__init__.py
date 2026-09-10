"""Astra tool-calling layer for the AIRA / SENTRY agents.

Astra (``gpt-6-astra`` via OpenAI's Responses API) reasons; **the application
executes tool calls**, and only ever read/propose ones. The model is never
handed an execution tool -- no ``transfer_funds`` / ``freeze_account`` /
``restrict_account`` / ``execute_contract`` schema exists anywhere in this
package, and ``tools.dispatch`` is default-deny.

Layout::

    personas.py            AIRA / SENTRY: actor id, system prompt, tool allow-list
    context.py             AstraInvocationContext -- the per-session binding
    errors.py              typed failures
    tools/
        schemas.py         the four OpenAI function-calling JSON schemas
        handlers.py        the four Python handlers (read / propose only)
        dispatch.py        execute_tool_call() -- forbidden-deny + default-deny
    sentry_screening.py    thin wrapper over the real SENTRY screening connector
    responses/
        client.py          Responses API transport (stubbed until the key lands)
        loop.py            run_agent_turn() -- the agentic loop
"""
