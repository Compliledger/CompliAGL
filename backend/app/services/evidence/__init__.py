"""Production-grade evidence layer for CompliAGL.

This package implements the runtime stages that run **after** Evidence
Requirement Resolution:

    Evidence Requirement Set
        -> Evidence Orchestration Plan
        -> Evidence Collection (via connectors)
        -> Raw Evidence
        -> Evidence Validation
        -> Normalized Evidence
        -> Canonical Evidence Package

Evidence is always **collected** from connector interfaces — it is never assumed
from intent fields, never fabricated, and mock connectors are never used
silently in production mode. Every evidence item carries provenance, receives a
validation result, and (when valid) is normalized into a platform-neutral
canonical schema. Sensitive payloads are never copied into public proof or
blockchain projections; only their hashes are.
"""
