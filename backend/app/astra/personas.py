"""AIRA / SENTRY persona definitions.

A persona binds a name to (1) the CompliAGL ``ActorIdentity`` it acts as,
(2) a system prompt, and (3) an **explicit** tool allow-list. Dispatch is
default-deny against that list -- a tool absent from ``allowed_tools`` is
refused before its handler runs (:class:`~app.astra.errors.ForbiddenToolError`).

The default actor ids are the HarborStone Demo #3 seed actors
(``app/db/seed.py``); a caller may override per session via
``AstraInvocationContext.actor_id``.

**SENTRY has no proposal power.** This is a hard boundary, not a cost choice:
giving the screening agent ``propose_governed_action`` would let a bounded,
delegated screening task widen itself into a consequential action, breaking the
AAI-001 bounded-delegation guarantee (AIRA delegates a narrow screening task to
SENTRY; SENTRY must not be able to act past it).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.db.seed import (
    HARBORSTONE_AIRA_ACTOR_ID,
    HARBORSTONE_SENTRY_ACTOR_ID,
)

# --- tool names (single source of truth; imported by schemas + dispatch) --- #
TOOL_GET_CASE_DATA = "get_case_data"
TOOL_GET_AUTHORIZED_TRANSACTION_HISTORY = "get_authorized_transaction_history"
TOOL_REQUEST_SANCTIONS_SCREENING = "request_sanctions_screening"
TOOL_PROPOSE_GOVERNED_ACTION = "propose_governed_action"

ALL_TOOL_NAMES: tuple[str, ...] = (
    TOOL_GET_CASE_DATA,
    TOOL_GET_AUTHORIZED_TRANSACTION_HISTORY,
    TOOL_REQUEST_SANCTIONS_SCREENING,
    TOOL_PROPOSE_GOVERNED_ACTION,
)

AIRA = "AIRA"
SENTRY = "SENTRY"


@dataclass(frozen=True)
class Persona:
    """An Astra persona and the tools it is allowed to call."""

    name: str
    default_actor_id: str
    system_prompt: str
    allowed_tools: tuple[str, ...]


_AIRA_SYSTEM_PROMPT = (
    "You are AIRA, an AML investigations assistant operating inside "
    "HarborStone's governance controls. You may read approved case data and "
    "authorized transaction history, and you may delegate a sanctions "
    "screening to SENTRY. When you determine a consequential action is "
    "warranted, call propose_governed_action -- that is the only way to act, "
    "and it is terminal: the proposal is evaluated by CompliIdentity and "
    "CompliAGL, escalated to a human approver when required, and executed by "
    "the application, not by you. You never execute anything yourself and you "
    "have no tool that moves funds, freezes, restricts, or executes a "
    "contract. Do not claim an action was taken -- report the governance "
    "decision you received."
)

_SENTRY_SYSTEM_PROMPT = (
    "You are SENTRY, a sanctions-screening agent. Your authority is bounded to "
    "screening the specific subject delegated to you. You may read approved "
    "case data and authorized transaction history to inform a screening "
    "judgement. You cannot propose, approve, or execute any action, and you "
    "have no tool to do so. Return a screening assessment only."
)

_PERSONAS: dict[str, Persona] = {
    AIRA: Persona(
        name=AIRA,
        default_actor_id=HARBORSTONE_AIRA_ACTOR_ID,
        system_prompt=_AIRA_SYSTEM_PROMPT,
        allowed_tools=(
            TOOL_GET_CASE_DATA,
            TOOL_GET_AUTHORIZED_TRANSACTION_HISTORY,
            TOOL_REQUEST_SANCTIONS_SCREENING,
            TOOL_PROPOSE_GOVERNED_ACTION,
        ),
    ),
    SENTRY: Persona(
        name=SENTRY,
        default_actor_id=HARBORSTONE_SENTRY_ACTOR_ID,
        system_prompt=_SENTRY_SYSTEM_PROMPT,
        allowed_tools=(
            TOOL_GET_CASE_DATA,
            TOOL_GET_AUTHORIZED_TRANSACTION_HISTORY,
        ),
    ),
}


def get_persona(name: str) -> Persona:
    """Return the persona by name (``"AIRA"`` / ``"SENTRY"``)."""
    try:
        return _PERSONAS[name]
    except KeyError:
        raise ValueError(
            f"unknown persona {name!r}; expected one of {sorted(_PERSONAS)}"
        ) from None


def persona_names() -> tuple[str, ...]:
    return tuple(_PERSONAS)
