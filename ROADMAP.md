# CompliAGL Roadmap

This roadmap distinguishes the **canonical target architecture** from what is
**implemented today**. Status labels reflect the repository as inspected, not
aspirations.

**Legend:** ✅ Implemented · 🧪 Prototype · ⚠️ Partial / adapter-ready ·
🚧 In development · 🧭 Planned

> **Overall project status:** Active development / proof of concept. The
> canonical runtime domain, deterministic decisioning, evidence lifecycle,
> execution authorization, and local AIProof generation/verification are
> implemented against a persistent (SQLite) store. Anchoring, external
> execution adapters, published SDKs, and real external integrations are
> partial, adapter-based, or planned.

## Phase 1 — Canonical Runtime Foundation

| Item | Status |
|------|--------|
| Persistent domain consolidation (SQLAlchemy models + Alembic migrations) | ✅ Implemented |
| Actor, Intent, Target, Operational Context as first-class objects | ✅ Implemented |
| Policy / decision engine consolidation (canonical services) | ✅ Implemented |
| Unified canonical AIProof model | ✅ Implemented |
| Retire deprecated in-memory MVP2 surface | 🚧 In development (MVP2 still mounted, marked deprecated) |

## Phase 2 — Executable Governance

| Item | Status |
|------|--------|
| CompliLedger executable-package intake (validate / approve / publish / supersede / retire) | ✅ Implemented |
| Policy resolution | ✅ Implemented |
| Applicability evaluation | ✅ Implemented |
| Control determination & evaluation | ✅ Implemented |
| Evidence lifecycle (orchestration → validation → normalization → sufficiency) | ✅ Implemented (with simulator connectors) |
| Assessment | ✅ Implemented |
| Deterministic decision | ✅ Implemented |
| Execution authorization (signed, TTL-bounded, consume/revoke) | ✅ Implemented |

## Phase 3 — Integration

| Item | Status |
|------|--------|
| TypeScript SDK (`@compliagl/sdk`) | 🧪 Prototype (source + tests, v0.1.0, unpublished) |
| Python SDK (`compliagl-sdk`) | 🧪 Prototype (source + tests, v0.1.0, unpublished) |
| External execution-result contract & ingestion | ✅ Implemented |
| Merchant / payment adapter interfaces | ⚠️ Partial / adapter-ready (interfaces; x402 + mock adapters only) |
| Hedera Agent Account adapter | 🧭 Planned (Hedera present only as an identity credential type) |
| Publish SDKs to npm / PyPI | 🧭 Planned |

## Phase 4 — Findings and Remediation

| Item | Status |
|------|--------|
| Findings generation | ✅ Implemented |
| Remediation planning & tracking | ✅ Implemented |
| DevSync dispatch | ⚠️ Partial / adapter-ready (in-memory adapter by default) |
| Resolution evidence collection & validation | ✅ Implemented |
| Re-assessment & deterministic re-decision | ✅ Implemented |

## Phase 5 — Proof Infrastructure

| Item | Status |
|------|--------|
| Signed AIProof (canonicalization + hashing + signing) | ✅ Implemented (RFC 8785 JCS, SHA-256, HMAC-SHA256 default) |
| Local independent verification (schema / hash / component / signature) | ✅ Implemented |
| Canonical proof package & CompliLedger handoff contract | ✅ Implemented (local handoff for dev; no external endpoint) |
| DLT anchoring (Algorand) | ⚠️ Partial / adapter-ready (optional external adapter; skipped when absent) |
| On-chain / independent-of-CompliAGL verification | 🧭 Planned |
| Hedera · Canton · XDC anchoring | 🧭 Planned (absent in code) |
| Asymmetric (e.g. Ed25519) proof signing | 🧭 Planned (interface is swappable) |

## Phase 6 — Continuous Assurance

| Item | Status |
|------|--------|
| ProofSync / AuditSync / RegSync event feeds (scoped, signed outbox) | ✅ Implemented (in-process outbox + delivery model) |
| Continuous monitoring & change detection | ✅ Implemented |
| Automated re-evaluation jobs | ✅ Implemented |
| Reusable operational assurance | 🚧 In development |
| Production authentication & hardening | 🧭 Planned (current auth is a placeholder) |
