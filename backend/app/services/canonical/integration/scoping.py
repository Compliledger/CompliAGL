"""Organization + role scoping enforcement for the sync portals.

Two independent scopes protect every feed:

* **Tenant (organization) scoping** is enforced structurally by the
  :class:`app.repositories.canonical.TenantRepository` base — every read is
  filtered by ``organization_id`` and a missing/mismatched tenant can never leak
  another organization's events.
* **Role scoping** is enforced here: a subscriber may only read a channel their
  role is contractually authorized for (auditors read AuditSync, regulators read
  RegSync, clients read ProofSync).
"""

from __future__ import annotations

from typing import Optional

from app.services.canonical.integration.contracts import (
    CHANNEL_AUTHORIZED_ROLES,
)
from app.utils.canonical_enums import IntegrationChannel, SubscriberRole


class ScopeError(Exception):
    """Raised when a caller is not authorized for the requested scope."""


def parse_channel(value: str) -> IntegrationChannel:
    """Resolve a channel name (case-insensitive) or raise :class:`ScopeError`."""
    try:
        return IntegrationChannel(str(value).strip().upper())
    except ValueError as exc:
        raise ScopeError(f"unknown integration channel: {value!r}") from exc


def parse_role(value: Optional[str]) -> SubscriberRole:
    """Resolve a subscriber role (case-insensitive) or raise :class:`ScopeError`."""
    if not value:
        raise ScopeError("a subscriber role is required")
    try:
        return SubscriberRole(str(value).strip().upper())
    except ValueError as exc:
        raise ScopeError(f"unknown subscriber role: {value!r}") from exc


def is_authorized(channel: IntegrationChannel, role: SubscriberRole) -> bool:
    """Return True iff ``role`` may read ``channel``."""
    return role in CHANNEL_AUTHORIZED_ROLES.get(channel, frozenset())


def authorize(channel: IntegrationChannel, role: SubscriberRole) -> None:
    """Raise :class:`ScopeError` unless ``role`` may read ``channel``."""
    if not is_authorized(channel, role):
        raise ScopeError(
            f"role {role.value} is not authorized for channel {channel.value}"
        )
