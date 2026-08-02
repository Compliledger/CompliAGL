"""Authorization invalidation — withdraw authorizations that no longer hold.

When a monitored change means the conditions that justified an authorization no
longer hold (expired/revoked evidence, revoked actor authority, a tightened
policy, an expired/revoked authorization, ...), any outstanding authorization for
the affected intent must be withdrawn *before* it can be consumed.

An authorization is never deleted. It is transitioned to a terminal state:
``EXPIRED`` for an expiry-driven change, otherwise ``REVOKED`` with a reason.
Already-terminal or already-consumed authorizations are left untouched.
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.orm import Session

from app.models.execution_authorization import ExecutionAuthorization
from app.repositories.canonical import ExecutionAuthorizationRepository
from app.services.canonical import authorization_service
from app.utils.canonical_enums import (
    AuthorizationStatus,
    MonitoringChangeType,
)
from app.utils.timestamps import utc_now

# Terminal / already-spent states that cannot be invalidated further.
_TERMINAL_STATES = {
    AuthorizationStatus.CONSUMED.value,
    AuthorizationStatus.REVOKED.value,
    AuthorizationStatus.EXPIRED.value,
}

_EXPIRY_CHANGE_TYPES = {
    MonitoringChangeType.AUTHORIZATION_EXPIRED.value,
    MonitoringChangeType.EVIDENCE_EXPIRED.value,
}


def _expire(
    db: Session,
    auth: ExecutionAuthorization,
    reason: Optional[str],
) -> ExecutionAuthorization:
    auth.status = AuthorizationStatus.EXPIRED.value
    auth.revoked_at = utc_now()
    auth.revocation_reason = reason
    return ExecutionAuthorizationRepository(db).save(auth)


def invalidate_authorization(
    db: Session,
    organization_id: str,
    authorization_id: str,
    *,
    change_type: Optional[str] = None,
    reason: Optional[str] = None,
) -> Optional[ExecutionAuthorization]:
    """Invalidate a single authorization. Returns it if a transition occurred."""
    repo = ExecutionAuthorizationRepository(db)
    auth = repo.get(organization_id, authorization_id)
    if auth is None or auth.status in _TERMINAL_STATES:
        return None
    if change_type in _EXPIRY_CHANGE_TYPES:
        return _expire(db, auth, reason)
    return authorization_service.revoke(
        db, organization_id, authorization_id, reason=reason
    )


def invalidate_authorizations(
    db: Session,
    organization_id: str,
    authorization_ids: Sequence[str],
    *,
    change_type: Optional[str] = None,
    reason: Optional[str] = None,
) -> list[str]:
    """Invalidate every live authorization in ``authorization_ids``.

    Returns the ids that were actually transitioned to a terminal state (already
    terminal / consumed authorizations are skipped).
    """
    invalidated: list[str] = []
    for authorization_id in authorization_ids:
        auth = invalidate_authorization(
            db,
            organization_id,
            authorization_id,
            change_type=change_type,
            reason=reason,
        )
        if auth is not None:
            invalidated.append(auth.id)
    return invalidated
