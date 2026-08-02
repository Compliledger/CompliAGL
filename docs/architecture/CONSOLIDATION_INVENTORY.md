# CompliAGL Architecture Consolidation — Inventory

This document is the pre-implementation inventory for **Phase 1: Architecture
Consolidation**. It records the duplicated implementations that existed in the
repository before consolidation, and identifies which implementation was
selected as canonical.

> Scope note: This phase is **architecture consolidation only**. Findings,
> remediation, DevSync, Hedera, ProofSync, AuditSync, RegSync and continuous
> monitoring are explicitly **out of scope** and are not implemented here.

## Canonical product boundary

CompliAGL is **AI-native execution governance infrastructure**. It does **not**
own merchant systems, booking systems, payment processing, wallets, settlement,
inventory, fulfillment, airline search, or product catalogs. External systems
perform the underlying action.

CompliAGL:

1. receives actor identity, intent, target, and operational context;
2. evaluates executable governance;
3. produces a deterministic decision (`APPROVED` / `DENIED` / `ESCALATED`);
4. issues execution authorization;
5. receives an external execution result;
6. generates an **AIProof**.

## 1. Duplicated implementations (before consolidation)

### 1.1 Actors / agents

| Implementation | Location | Persistence | Status |
| --- | --- | --- | --- |
| `Agent` ORM model + `agent_service` | `app/models/agent.py`, `app/services/agent_service.py` | SQLAlchemy (persistent) | **Canonical** |
| In-memory actor registry | `app/mvp2/identity/actors.py` (`_ACTOR_REGISTRY`) | in-memory dict, seeded on boot | **Deprecated** |

### 1.2 Policies

| Implementation | Location | Persistence | Status |
| --- | --- | --- | --- |
| `Policy` ORM model + `policy_service` | `app/models/policy.py`, `app/services/policy_service.py` | SQLAlchemy (persistent) | **Canonical** |
| In-memory policy store | `app/mvp2/core/policy_engine.py` (`_POLICY_STORE`) | in-memory dict, seeded on boot | **Deprecated** |

### 1.3 Deterministic rule evaluation / policy engines (duplicated)

| Engine | Location | Notes | Status |
| --- | --- | --- | --- |
| `rule_engine` (15 sequential rules) | `app/utils/rule_engine.py` + `app/services/evaluation_service.py` | Transaction-centric, persistent-policy aware | **Deprecated** (transaction-centric, not canonical) |
| `evaluate_policies` (rules-dict engine) | `app/mvp2/core/policy_engine.py` | Intent-centric, simple rules dict | **Selected rule core** |
| `decision_engine.evaluate` | `app/mvp2/core/decision_engine.py` | Orchestrator over `evaluate_policies` | Superseded by canonical `app/services/decision_engine.py` |

**Consolidated into:** `app/services/decision_engine.py` — a single,
intent-based deterministic decision engine that reads **persistent** policies
and evaluates them with one rule core.

### 1.4 Decisions

Both engines produced overlapping outcomes. The canonical outcome set is
preserved: **`APPROVED`, `DENIED`, `ESCALATED`** (the extra
`PENDING_APPROVAL` enum member is retained for backward compatibility but the
canonical engine only returns the three canonical outcomes).

### 1.5 Proof models (duplicated)

| Proof model | Location | Persistence | Status |
| --- | --- | --- | --- |
| `ProofBundle` ORM | `app/models/proof_bundle.py`, `app/services/proof_service.py`, `app/schemas/proof_bundle.py` | SQLAlchemy (persistent), transaction-scoped | **Deprecated** |
| `AIProofBundle` (Pydantic) | `app/mvp2/schemas/aiproof.py`, `app/mvp2/proof/aiproof.py` | legacy x402 demo bundle, persisted via `ai_proofs` | **Deprecated (legacy x402 demo)** |
| `ProofResponse` (MVP2 route store) | `app/mvp2/api/routes/proof.py` (`_PROOF_STORE`) | in-memory dict | **Deprecated** |
| **`AIProof`** (Pydantic) | `app/schemas/canonical/aiproof.py`, `app/services/canonical/aiproof/` | SQLAlchemy `canonical_ai_proofs` via `CanonicalAIProof` | **Canonical** |

**Consolidated into:** the single canonical **AIProof**
(`app/schemas/canonical/aiproof.py::AIProof`), persisted via
`app/models/canonical_aiproof.py::CanonicalAIProof` and
`app/services/canonical/aiproof/`. It covers the complete governance lifecycle
(approved+executed, approved-but-failed, denied, escalated, remediated+
re-evaluated, terminated), stores canonical projections + references (evidence
is referenced by id/hash/classification/validation-outcome/secure-retrieval
reference, never embedded), is canonicalized with **RFC 8785 (JCS)**, hashed with
**SHA-256** and **digitally signed**, publishes a **versioned JSON Schema**, and
is handed to CompliLedger through the formal `CompliLedgerProofHandoff`. The
earlier `ProofBundle` and `AIProofBundle` records are deprecated; the
`ai_proofs` table remains only for the compli402 x402 hackathon-demo flow.

### 1.6 Execution adapters / x402 coupling

| Component | Location | Issue |
| --- | --- | --- |
| Execution service | `app/mvp2/execution/service.py` | Silently substituted `amount=0` and `currency="USD"` — **corrected** |
| Adapter interface | `app/mvp2/execution/adapters/base.py` | OK, retained |
| `MockExecutionAdapter` | `app/mvp2/execution/adapters/mock.py` | OK, retained |
| `SolanaExecutionAdapter` | `app/mvp2/execution/adapters/solana.py` | Stub, retained |
| `X402Adapter` | `app/mvp2/execution/adapters/x402.py` | Was treated as the runtime definition — now **one optional adapter** |

### 1.7 In-memory runtime dependencies (removed from production path)

| Store | Location | Replacement |
| --- | --- | --- |
| `_ACTOR_REGISTRY` | `app/mvp2/identity/actors.py` | persistent `agents` table via `actor_registry` |
| `_POLICY_STORE` | `app/mvp2/core/policy_engine.py` | persistent `policies` table via `policy_repository` |
| `_PROOF_STORE` (compli402) | `app/api/routes/compli402.py` | persistent `ai_proofs` table via `aiproof_service` |
| `_PROOF_STORE` (mvp2 proof route) | `app/mvp2/api/routes/proof.py` | deprecated; canonical proofs are persistent |

### 1.8 Generic transaction model

`app/models/transaction.py` plus the MVP1 `/transactions` evaluate flow model a
**generic financial transaction** (vendor / chain / asset / destination). This
does not represent the canonical CompliAGL boundary (actor → intent → decision →
authorization → external execution → AIProof). The transaction-centric
evaluation path is **deprecated** in favour of the intent-based decision engine.
The ORM tables remain for backward compatibility.

## 2. Canonical selections (summary)

| Concern | Canonical implementation |
| --- | --- |
| Actor / agent | `Agent` ORM (`agents` table) + `app/services/actor_registry.py` |
| Policy | `Policy` ORM (`policies` table) + `app/services/policy_repository.py` |
| Deterministic evaluation | `app/services/decision_engine.py` (one engine, one rule core) |
| Decision outcomes | `APPROVED` / `DENIED` / `ESCALATED` |
| Proof | `AIProof` (`app/schemas/canonical/aiproof.py`) persisted via `CanonicalAIProof` (`canonical_ai_proofs` table) + `app/services/canonical/aiproof/`. Legacy `ProofBundle` and x402 `AIProofBundle` deprecated. |
| Execution | Adapter pattern; CompliAGL authorizes, external systems execute and return a result that CompliAGL validates + records |
| x402 | One **optional** execution adapter (`X402Adapter`) |

## 3. Acceptance-criteria mapping

| Criterion | How it is satisfied |
| --- | --- |
| One active persistent actor implementation | `agents` table via `actor_registry`; in-memory registry deprecated |
| One active persistent policy implementation | `policies` table via `policy_repository`; in-memory store deprecated |
| One active decision engine | `app/services/decision_engine.py`; MVP2 engine shimmed/deprecated |
| One canonical AIProof implementation | Single `AIProof` (`app/schemas/canonical/aiproof.py`) + `CanonicalAIProof` ORM + `app/services/canonical/aiproof/`; `ProofBundle` and legacy x402 `AIProofBundle` deprecated |
| Runtime state survives restart | actors, policies and proofs are all persisted in SQLAlchemy |
| x402 is an adapter, not the core | `X402Adapter` registered as one optional adapter |
| External execution separated from governance | decision (governance) and execution adapters are distinct layers |
| No production path depends on in-memory seed | startup seeds the **database**; in-memory seeds are deprecated |
