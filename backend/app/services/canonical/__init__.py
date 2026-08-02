"""Service layer for canonical first-class runtime domain objects.

Services own business rules: identifier immutability, JSON (de)serialization,
integrity hashing, idempotency, tenant validation, and lifecycle-transition
enforcement. They delegate all persistence to tenant-scoped repositories.
"""
