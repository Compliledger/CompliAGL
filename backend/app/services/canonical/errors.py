"""Typed errors for the canonical service layer."""

from __future__ import annotations


class CanonicalError(Exception):
    """Base class for canonical service errors."""


class NotFoundError(CanonicalError):
    """A referenced canonical resource does not exist in the tenant."""


class OrganizationNotFoundError(NotFoundError):
    """The given ``organization_id`` does not name a real, active tenant."""

    def __init__(self, organization_id: str) -> None:
        self.organization_id = organization_id
        super().__init__(f"Unknown organization_id: {organization_id!r}")


class ConflictError(CanonicalError):
    """A uniqueness/idempotency constraint was violated."""


class AuthorityVerificationError(CanonicalError):
    """An approver's authority could not be verified against CompliIdentity.

    Fail-closed: raised whenever an approval action cannot be tied to a
    principal whose authority to approve *this* action is confirmed right now
    (unconfigured client, unavailable/known-denied authority context, not
    ``sufficient``, a non-human approver, or self-approval). ``reason`` carries
    the specific machine code.
    """

    def __init__(self, reason: str, detail: str = "") -> None:
        self.reason = reason
        super().__init__(detail or reason)


class InvalidTransitionError(CanonicalError):
    """An illegal lifecycle status transition was attempted."""

    def __init__(self, entity: str, current: str, requested: str) -> None:
        self.entity = entity
        self.current = current
        self.requested = requested
        super().__init__(
            f"Invalid {entity} transition: {current} -> {requested}"
        )


class PackageValidationError(CanonicalError):
    """A governance package failed contract validation."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__("; ".join(errors) if errors else "package validation failed")


class PackageImmutableError(CanonicalError):
    """An attempt was made to mutate immutable/published package content."""


class PackageSignatureError(CanonicalError):
    """A governance package presented an invalid or missing signature."""
