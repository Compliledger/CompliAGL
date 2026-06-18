# CompliAGL

> **The Control Plane for Governed Autonomous Execution**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

**Authorize first. Execute second. Prove permanently.**

**CompliAGL is the control plane for governed autonomous execution.** It decides
what an autonomous actor is allowed to do *before* it acts, executes approved
actions through pluggable adapters, and produces a verifiable **AIProof** for
every outcome. **Compli402** is the x402-powered governed payment layer built on
top of that control plane: it gates approved actions behind an x402 "HTTP 402
Payment Required" flow and anchors each AIProof on **Algorand** through the
existing `compliledger-algorand-adapter`.

---

## Why CompliAGL

AI agents and autonomous systems can now initiate financial transactions, call
APIs, and trigger operational actions on their own. That capability is powerful —
and unsupervised, it is a liability.

- **Execution without governance creates risk.** An actor that can move funds or
  invoke production APIs needs explicit, enforceable boundaries before it acts.
- **Logs are not enough.** A log tells you what happened *after* the fact. It
  cannot stop a disallowed action, and it cannot be independently verified.
- **CompliAGL closes the gap.** It enforces policy *before* execution and
  produces cryptographic proof *after* execution — turning autonomous activity
  into something authorized, traceable, and verifiable.

---

## Two layers

| Layer | What it is | Status |
|-------|------------|--------|
| **CompliAGL** | The control plane for governed autonomous execution: identity, policy/decision engine, execution adapters, and AIProof generation. | **Live now** |
| **Compli402** | The x402-powered governed payment layer. Gates approved actions behind an x402 payment, then executes, generates an AIProof, and anchors it on Algorand. | **Live now** |

Compli402 is exposed as a small, demo-ready public API under
`/api/compli402` and is the surface used for the Global x402 Challenge.

---

## Competition Demo Flow

The Compli402 flow runs end-to-end, locally, with no external services or
secrets (a mock x402 facilitator and an in-memory proof store are used by
default):

```
Actor → Intent → Policy Decision → x402 Payment → Execution → AIProof → Algorand Anchor
```

1. **Actor** — a verifiable actor (e.g. the seeded `TravelAgent-01`) submits an intent.
2. **Intent** — an action, amount, and currency the actor wants to perform.
3. **Policy Decision** — CompliAGL evaluates governance policy and returns
   `APPROVE`, `DENY`, or `ESCALATE`.
4. **x402 Payment** — an approved action requires an x402 payment; without one,
   a `402 Payment Required` response is returned describing how to pay.
5. **Execution** — once the payment is verified, the approved action is executed.
6. **AIProof** — an AIProof bundle is generated and deterministically hashed.
7. **Algorand Anchor** — the AIProof is anchored on Algorand through the shared
   `compliledger-algorand-adapter`, and the anchor receipt is returned.

### Try it

```bash
# 1. Approved + paid → executes, generates AIProof, anchors on Algorand
curl -X POST http://localhost:8000/api/compli402/execute \
  -H "Content-Type: application/json" \
  -d '{"actor_id":"00000000-0000-0000-0000-000000000001",
       "action":"book_flight","amount":100,"currency":"USDC",
       "payment":{"reference":"pay-demo-001"}}'

# 2. Approved but unpaid → HTTP 402 Payment Required
curl -i -X POST http://localhost:8000/api/compli402/execute \
  -H "Content-Type: application/json" \
  -d '{"actor_id":"00000000-0000-0000-0000-000000000001",
       "action":"book_flight","amount":100,"currency":"USDC"}'
```

---

## AIProof Bundle

Every executed action produces an AIProof bundle with a deterministic
`proof_hash`. Post-hash fields (`anchor_tx_id`, `verification_url`) are
populated *after* hashing and are therefore excluded from the hash itself, so
the same logical execution always yields the same `proof_hash`.

| Field | Description |
|-------|-------------|
| `proof_id` | Unique identifier for the proof. |
| `proof_type` | Kind of proof (e.g. `compli402.execution`). |
| `actor_id` / `actor_identity` | The acting entity and its resolved identity. |
| `intent_id` / `intent` | The governed intent. |
| `policy_id` / `policy_version` | The governing policy and its version. |
| `decision` / `decision_reason` | The governance decision and reason codes. |
| `execution_adapter` / `execution_status` | How the action was executed and its outcome. |
| `payment_protocol` / `payment_reference` | The payment protocol (`x402`) and settlement reference. |
| `settlement_chain` | Network the payment settled on. |
| `anchor_chain` / `anchor_tx_id` | Anchoring chain (`algorand`) and on-chain tx id (post-hash). |
| `proof_hash` | Deterministic SHA-256 hash binding the bundle. |
| `created_at` | ISO 8601 UTC creation timestamp. |
| `verification_url` | URL to verify the proof (post-hash). |

---

## Algorand Anchoring

Algorand anchoring is **not reimplemented** here. CompliAGL is a thin
integration layer: it maps an AIProof bundle onto the canonical proof schema of
the existing **`compliledger-algorand-adapter`** and delegates anchoring and
verification to that adapter (see
`backend/app/mvp2/anchor/algorand_adapter_service.py`).

The shared adapter is an **optional dependency**, imported lazily. When it is
not installed, the Compli402 flow still completes and returns a structured,
non-fatal anchor receipt — so the demo always runs. See
`backend/app/mvp2/anchor/README.md` for installation instructions.

---

## Capability Status

We are deliberately precise about what is real today versus what is planned. The
following items are **placeholders / aspirational** and are **not** claimed as
working integrations: Solana settlement, XRPL, Base, Hedera, and Canton.

### Live now

- **CompliAGL control plane** — actor identity, policy/decision engine
  (`APPROVE` / `DENY` / `ESCALATE`), reason codes.
- **Compli402** — x402 governed payment layer (`/api/compli402`) with a mock
  facilitator for local development.
- **x402 execution adapter** — payment-gated execution (`402 Payment Required`
  until payment is verified).
- **AIProof generation** — deterministic, post-hash-excluding proof bundles.
- **Algorand anchoring** — via the existing `compliledger-algorand-adapter`
  (degrades gracefully when the adapter is absent).
- **Demo dashboard** — minimal React + Vite frontend visualising the full flow.

### In progress

- **HTTP x402 facilitator** — verification against a live facilitator endpoint
  (the abstraction exists; the mock is the default).
- **Persistent storage** — proofs and actors are currently in-memory.
- **MVP 2 actor / policy management APIs** — dedicated CRUD surfaces.

### Planned

- **Additional settlement layers** — Solana, XRPL, Base (adapter stubs / future work).
- **Additional anchoring / verification networks** — Hedera, Canton.
- **CompliAGL Identity** — full DID / VC actor identity.
- **CompliAGL Graph & Network** — cross-actor traceability and an external
  verification layer for auditors and counterparties.

---

## Architecture

```
AI Agent / Autonomous Actor
        ↓
Actor Identity
        ↓
Intent
        ↓
CompliAGL Core (policy + decision)
        ↓
Decision:
  APPROVE  → continue
  DENY     → stop
  ESCALATE → human approval
        ↓ (if APPROVED)
Compli402 — x402 Payment (HTTP 402 until verified)
        ↓
Execution Adapter
        ↓
AIProof (deterministic hash)
        ↓
Algorand Anchor (via compliledger-algorand-adapter)
```

---

## Quick Start

**Backend**

```bash
git clone https://github.com/Compliledger/CompliAGL.git
cd CompliAGL/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API will be available at **http://localhost:8000** and interactive docs at
**http://localhost:8000/docs**.

**Frontend**

```bash
cd frontend
cp .env.example .env          # set VITE_API_BASE_URL (defaults to localhost:8000)
npm install
npm run dev
```

The demo dashboard will be available at **http://localhost:5173**.

**Tests**

```bash
cd backend
pip install -r requirements.txt
pytest
```

---

## API Overview

The backend is a FastAPI service. Interactive Swagger docs are always available
at **`/docs`**.

**Compli402 (x402 challenge surface)**

- `GET /api/compli402/health` — service health and x402 configuration.
- `POST /api/compli402/verify/intent` — evaluate an intent against policy (no execution).
- `POST /api/compli402/execute` — full governance → payment → execute → AIProof → anchor flow.
- `GET /api/compli402/proofs/latest` — most recent AIProof bundle.
- `GET /api/compli402/proofs/{proof_hash}` — a single AIProof bundle by hash.

**Governance & proof (MVP 1)**

- `GET /health` — service health check.
- `POST /api/agents` · `GET /api/agents` — register and list actors/agents.
- `POST /api/policies` · `GET /api/policies` — manage governance policies.
- `POST /api/transactions` · `POST /api/transactions/{id}/evaluate` — submit and evaluate intents.
- `GET /api/audit` — browse the audit trail.
- `GET /api/proofs` — retrieve generated proof bundles.
- `GET /api/dashboard/summary` — control-plane summary metrics.

See `/docs` for full request/response schemas.

---

## Repository Structure

```
CompliAGL/
├── backend/            # FastAPI control-plane service
│   ├── app/
│   │   ├── api/routes/compli402.py     # Compli402 x402 public API
│   │   └── mvp2/
│   │       ├── core/                   # policy + decision engine
│   │       ├── execution/adapters/     # x402 (+ mock, solana stub) adapters
│   │       ├── proof/                  # AIProof generation + hashing
│   │       └── anchor/                 # compliledger-algorand-adapter wrapper
│   ├── tests/
│   ├── requirements.txt
│   ├── Procfile
│   └── railway.json
├── frontend/           # React + Vite Compli402 demo dashboard
├── docs/               # Architecture and demo-flow documentation
├── README.md
└── LICENSE
```

---

## Deployment

CompliAGL deploys to **Railway**. The backend ships with a `Procfile` and
`railway.json` (NIXPACKS builder) that start the FastAPI service via uvicorn,
binding to the platform-provided `$PORT`.

---

## License

Released under the [MIT License](./LICENSE).
