"""Shared dependencies for the v1 API.

Tenant isolation is enforced at the transport boundary: every read/transition
endpoint requires an ``organization_id``, supplied either via the
``X-Organization-Id`` header or an ``organization_id`` query parameter.
"""

from __future__ import annotations

from typing import Optional

from fastapi import Header, HTTPException, Query


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
