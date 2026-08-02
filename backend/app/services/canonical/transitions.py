"""Lifecycle state machines and transition validation.

Each canonical resource with a lifecycle declares the set of legal successor
states. :func:`validate_transition` is the single enforcement point; illegal
transitions raise :class:`InvalidTransitionError`.
"""

from __future__ import annotations

from app.services.canonical.errors import InvalidTransitionError
from app.utils.canonical_enums import AuthorizationStatus, IntentStatus

# Intent lifecycle.
INTENT_TRANSITIONS: dict[str, set[str]] = {
    IntentStatus.PENDING.value: {
        IntentStatus.SUBMITTED.value,
        IntentStatus.CANCELLED.value,
    },
    IntentStatus.SUBMITTED.value: {
        IntentStatus.EVALUATED.value,
        IntentStatus.DENIED.value,
        IntentStatus.EXPIRED.value,
        IntentStatus.CANCELLED.value,
    },
    IntentStatus.EVALUATED.value: {
        IntentStatus.AUTHORIZED.value,
        IntentStatus.DENIED.value,
        IntentStatus.EXPIRED.value,
    },
    IntentStatus.AUTHORIZED.value: {
        IntentStatus.EXECUTED.value,
        IntentStatus.EXPIRED.value,
    },
    IntentStatus.EXECUTED.value: set(),
    IntentStatus.DENIED.value: set(),
    IntentStatus.EXPIRED.value: set(),
    IntentStatus.CANCELLED.value: set(),
}

# Execution authorization lifecycle.
AUTHORIZATION_TRANSITIONS: dict[str, set[str]] = {
    AuthorizationStatus.PENDING.value: {
        AuthorizationStatus.AUTHORIZED.value,
        AuthorizationStatus.REVOKED.value,
    },
    AuthorizationStatus.AUTHORIZED.value: {
        AuthorizationStatus.CONSUMED.value,
        AuthorizationStatus.REVOKED.value,
        AuthorizationStatus.EXPIRED.value,
    },
    AuthorizationStatus.CONSUMED.value: set(),
    AuthorizationStatus.REVOKED.value: set(),
    AuthorizationStatus.EXPIRED.value: set(),
}


def validate_transition(
    entity: str, transitions: dict[str, set[str]], current: str, requested: str
) -> None:
    """Raise :class:`InvalidTransitionError` if the transition is illegal.

    A no-op transition (``current == requested``) is always rejected so callers
    cannot silently re-apply a terminal state.
    """
    allowed = transitions.get(current, set())
    if requested not in allowed:
        raise InvalidTransitionError(entity, current, requested)
