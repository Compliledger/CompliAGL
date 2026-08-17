"""Organization (tenant) registry checks.

Single source of truth for "is this organization_id real" — used both at the
API boundary (``app.api.v1.deps.get_org_id``) and at the repository layer
(``app.repositories.canonical.TenantRepository``), so every read and write
path validates against the same rule regardless of whether the caller
supplied ``organization_id`` via header, query param, or request body.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.services.canonical.errors import OrganizationNotFoundError


def exists_active(db: Session, organization_id: str) -> bool:
    """True if ``organization_id`` names a real, ACTIVE organization."""
    org = db.get(Organization, organization_id)
    return org is not None and org.status == "ACTIVE"


def require_active(db: Session, organization_id: str) -> None:
    """Raise :class:`OrganizationNotFoundError` unless the tenant is real and active."""
    if not exists_active(db, organization_id):
        raise OrganizationNotFoundError(organization_id)
