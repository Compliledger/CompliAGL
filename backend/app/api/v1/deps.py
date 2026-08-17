"""Shared dependencies for the v1 API.

Tenant isolation is enforced at the transport boundary: every read/transition
endpoint requires an ``organization_id``, supplied either via the
``X-Organization-Id`` header or an ``organization_id`` query parameter.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Depends, Header, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.canonical import organization_service

# Roles permitted to author (create) executable governance packages. Only
# CompliLedger service identities or authorized governance administrators may
# publish governance into CompliAGL.
PACKAGE_AUTHOR_ROLES = frozenset(
    {"COMPLILEDGER_SERVICE", "GOVERNANCE_ADMIN"}
)


def get_org_id(
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    organization_id: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
) -> str:
    """Resolve and validate the caller's tenant.

    Prefers the header over the query param. The resolved value must name a
    real, active :class:`~app.models.organization.Organization` — an unknown
    or inactive ``organization_id`` is rejected here rather than silently
    accepted.
    """
    org = x_organization_id or organization_id
    if not org:
        raise HTTPException(
            status_code=400,
            detail="organization_id is required (X-Organization-Id header or query param).",
        )
    if not organization_service.exists_active(db, org):
        raise HTTPException(
            status_code=404,
            detail=f"Unknown organization_id: {org!r}",
        )
    return org


def require_package_author(
    x_governance_role: Optional[str] = Header(
        default=None, alias="X-Governance-Role"
    ),
) -> str:
    """Authorize the caller to create governance packages.

    The caller must present an ``X-Governance-Role`` header identifying a
    CompliLedger service identity or a governance administrator. Any other
    caller is rejected with ``403``.
    """
    role = (x_governance_role or "").strip().upper()
    if role not in PACKAGE_AUTHOR_ROLES:
        raise HTTPException(
            status_code=403,
            detail=(
                "Only CompliLedger service identities or authorized governance "
                "administrators may create governance packages "
                "(set X-Governance-Role)."
            ),
        )
    return role


def get_subscriber_role(
    x_subscriber_role: Optional[str] = Header(
        default=None, alias="X-Subscriber-Role"
    ),
    subscriber_role: Optional[str] = Query(default=None),
) -> str:
    """Resolve the caller's sync-portal subscriber role.

    Role scoping for the ProofSync / AuditSync / RegSync feeds is enforced from
    this value (see ``app.services.canonical.integration.scoping``). The role is
    supplied via the ``X-Subscriber-Role`` header or a ``subscriber_role`` query
    parameter.
    """
    role = x_subscriber_role or subscriber_role
    if not role:
        raise HTTPException(
            status_code=400,
            detail=(
                "subscriber role is required "
                "(X-Subscriber-Role header or subscriber_role query param)."
            ),
        )
    return role
