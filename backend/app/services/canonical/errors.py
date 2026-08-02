"""Typed errors for the canonical service layer."""

from __future__ import annotations


class CanonicalError(Exception):
    """Base class for canonical service errors."""


class NotFoundError(CanonicalError):
    """A referenced canonical resource does not exist in the tenant."""


class ConflictError(CanonicalError):
    """A uniqueness/idempotency constraint was violated."""


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
