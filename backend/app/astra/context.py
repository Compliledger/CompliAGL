"""The per-session binding every tool handler runs against.

``AstraInvocationContext`` is constructed by the application (never by the
model) and injected as the first argument of every tool handler by
``tools.dispatch``. It pins the session to one organization, one persona, one
acting ``ActorIdentity`` and **one case** -- handlers refuse a model-supplied
``case_id`` / ``resource_instance`` that does not match ``case_id`` here, so the
model cannot pivot to another case.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field

from sqlalchemy.orm import Session

from app.astra.personas import Persona, get_persona


@dataclass
class AstraInvocationContext:
    """Immutable-by-convention session context for a single agent turn."""

    db: Session
    organization_id: str
    persona: Persona
    case_id: str
    actor_id: str
    correlation_id: str = field(default_factory=lambda: f"astra-{uuid.uuid4()}")


def build_context(
    db: Session,
    *,
    organization_id: str,
    persona_name: str,
    case_id: str,
    actor_id: str | None = None,
    correlation_id: str | None = None,
) -> AstraInvocationContext:
    """Construct a context, defaulting the actor id to the persona's seed actor."""
    persona = get_persona(persona_name)
    ctx = AstraInvocationContext(
        db=db,
        organization_id=organization_id,
        persona=persona,
        case_id=case_id,
        actor_id=actor_id or persona.default_actor_id,
    )
    if correlation_id:
        ctx.correlation_id = correlation_id
    return ctx
