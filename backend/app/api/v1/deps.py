"""Shared dependencies for the v1 API.

Tenant isolation is enforced at the transport boundary: every read/transition
endpoint requires an ``organization_id``, supplied either via the
``X-Organization-Id`` header or an ``organization_id`` query parameter.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, Query


# Roles permitted to author (create) executable governance packages. Only
# CompliLedger service identities or authorized governance administrators may
# publish governance into CompliAGL.
PACKAGE_AUTHOR_ROLES = frozenset(
    {"COMPLILEDGER_SERVICE", "GOVERNANCE_ADMIN"}
)


def get_org_id(
    x_organization_id: Optional[str] = Header(default=None, alias="X-Organization-Id"),
    organization_id: Optional[str] = Query(default=None),
) -> str:
    """Resolve the caller's tenant, preferring the header over the query param."""
    org = x_organization_id or organization_id
    if not org:
        raise HTTPException(
            status_code=400,
            detail="organization_id is required (X-Organization-Id header or query param).",
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
