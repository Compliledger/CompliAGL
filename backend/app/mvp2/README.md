# CompliAGL — MVP 2

## What is MVP 2?

MVP 2 is the **advanced governance module** for CompliAGL. It introduces a
pipeline-based architecture that cleanly separates identity resolution, policy
evaluation, transaction execution, and cryptographic proof generation into
discrete, composable stages.

## How it differs from MVP 1

| Aspect | MVP 1 | MVP 2 |
|--------|-------|-------|
| Architecture | Monolithic service layer with tightly-coupled CRUD routes | Pipeline: Actor → Identity → Decision → Execution → Proof |
| Execution | No on-chain execution — decisions are stored locally | Adapter-based execution layer (mock, Solana stub) |
| Proof model | Basic proof bundle via hashing utilities | Canonical `ProofPayload` → SHA-256 digest with full audit metadata |
| Policy engine | Rule engine embedded in transaction service | Standalone `policy_engine` + `decision_engine` with reason codes |
| Identity | Agents table (DB-backed) | Lightweight actor model (`AGENT`, `HUMAN`, `ORGANIZATION`) |

## Architecture

Every transaction flows through a five-stage pipeline:

```
Actor ──▶ Identity ──▶ Decision ──▶ Execution ──▶ Proof
```

1. **Actor** — The entity initiating the transaction (agent, human, or org).
   Defined in `identity/actors.py` with schemas in `schemas/actor.py`.
2. **Identity** — Resolves and validates the actor. Currently an in-memory
   factory; production would integrate a persistent identity store.
3. **Decision** — The `decision_engine` calls the `policy_engine` to evaluate
   active policies against the transaction. Returns `APPROVED`, `DENIED`,
   `ESCALATED`, or `PENDING_APPROVAL` along with machine-readable reason codes.
4. **Execution** — Dispatches approved transactions to a blockchain adapter via
   `execution/service.py`. The adapter is selected by name (`mock`, `solana`).
5. **Proof** — Builds a canonical `ProofPayload`, serializes it to sorted JSON,
   and produces a SHA-256 hex digest. The proof bundle is returned to the
   caller for audit anchoring.

## Current adapters

All adapters implement `BaseExecutionAdapter` (`execution/adapters/base.py`).

| Adapter | Module | Status |
|---------|--------|--------|
| **mock** | `execution/adapters/mock.py` | Fully functional — returns a simulated `CONFIRMED` status with a random tx hash. |
| **solana** | `execution/adapters/solana.py` | Stub — returns `PENDING` with an error message. Ready for Solana RPC integration. |

Register new adapters in `_ADAPTER_REGISTRY` inside `execution/service.py`.

## Current proof model

```
ProofRequest
  ├── transaction_id   (UUID)
  ├── decision_result  (str)
  ├── reason_codes     (list[str])
  └── metadata         (dict | None)
        │
        ▼
ProofPayload  (canonical structure)
  ├── transaction_id
  ├── decision_result
  ├── reason_codes
  ├── timestamp        (ISO 8601 UTC)
  └── metadata
        │
        ▼  sha256(json.dumps(sorted_keys))
ProofResponse
  ├── transaction_id
  ├── proof_hash       (hex digest)
  ├── status           (GENERATED | ANCHORED | FAILED)
  ├── payload          (dict)
  └── metadata
```

Hashing logic lives in `proof/hashing.py`; generation in `proof/generator.py`.

## Current endpoints

All MVP 2 routes are mounted under the `/api/v2` prefix.

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v2/decisions/` | Evaluate a transaction against active policies |
| POST | `/api/v2/executions/` | Execute an approved transaction via an adapter |
| POST | `/api/v2/proofs/` | Generate a cryptographic proof bundle |

> **Note:** Actor and policy management currently use the MVP 1 endpoints
> (`/api/agents/`, `/api/policies/`). Dedicated MVP 2 CRUD routes for actors
> and policies are planned.

## Module layout

```
mvp2/
├── api/routes/
│   ├── decision.py        # POST /api/v2/decisions/
│   ├── execution.py       # POST /api/v2/executions/
│   └── proof.py           # POST /api/v2/proofs/
├── core/
│   ├── decision_engine.py # Orchestrates policy evaluation
│   ├── policy_engine.py   # Rule matching (max_amount, denied_currencies, escalation)
│   └── reason_codes.py    # Machine-readable reason code constants
├── execution/
│   ├── adapters/
│   │   ├── base.py        # Abstract adapter interface
│   │   ├── mock.py        # In-memory mock adapter
│   │   └── solana.py      # Solana stub adapter
│   └── service.py         # Adapter registry & dispatch
├── identity/
│   └── actors.py          # Actor factory & lookup helpers
├── proof/
│   ├── generator.py       # Proof bundle builder
│   ├── hashing.py         # SHA-256 canonical hashing
│   └── schema.py          # ProofPayload model
└── schemas/
    ├── actor.py           # ActorCreate, ActorRead, ActorType
    ├── decision.py        # DecisionRequest, DecisionResponse, DecisionResult
    ├── execution.py       # ExecutionRequest, ExecutionResponse, ExecutionStatus
    ├── policy.py          # PolicyCreate, PolicyRead, PolicyStatus
    ├── proof.py           # ProofRequest, ProofResponse, ProofStatus
    └── transaction.py     # TransactionCreate, TransactionRead, TransactionStatus
```
