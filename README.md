# CompliAGL

> **The Control Plane for Autonomous Execution**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

**Authorize first. Execute second. Prove permanently.**

CompliAGL is the control plane for autonomous execution. It governs what autonomous actors are allowed to do *before* they act, executes approved actions through configurable adapters, and generates verifiable proof for every outcome. CompliAGL is **chain-agnostic and payment-rail agnostic** — no single blockchain, settlement layer, or payment protocol is assumed.

---

## Why CompliAGL

AI agents and autonomous systems can now initiate financial transactions, call APIs, and trigger operational actions on their own. That capability is powerful — and unsupervised, it is a liability.

- **Execution without governance creates risk.** An actor that can move funds or invoke production APIs needs explicit, enforceable boundaries before it acts.
- **Logs are not enough.** A log tells you what happened *after* the fact. It cannot stop a disallowed action, and it cannot be independently verified.
- **CompliAGL closes the gap.** It enforces policy *before* execution and produces cryptographic proof *after* execution — turning autonomous activity into something that is authorized, traceable, and verifiable.

Pre-execution policy enforcement decides whether an action is allowed. Post-execution proof makes the outcome permanent and auditable.

---

## What CompliAGL Does

Every autonomous action flows through a single, consistent control path:

```
Actor → Identity → Intent → Policy Decision → Execution → AIProof → State Snapshot → Anchoring → Proof Graph → Compliance Proof Network
```

An actor presents a verifiable identity and an intent. CompliAGL evaluates that intent against policy and returns a decision. Approved actions are executed through an adapter, the result is wrapped in an AIProof bundle, a state snapshot is captured, and proof/state hashes are anchored. Every link is connected in a proof graph that can ultimately be verified across a compliance proof network.

---

## Core Capabilities

| Module | Responsibility |
|--------|----------------|
| **CompliAGL Core** | Policy and decision engine — evaluates intents and returns `APPROVE`, `DENY`, or `ESCALATE`. |
| **CompliAGL Execute** | Execution adapters for x402, Solana, and mock execution, with future XRPL / Base / others. |
| **CompliAGL Proof** | AIProof bundles capturing the verifiable record of each execution. |
| **CompliAGL Identity** | Actor model with DID / VC support for verifiable actor identity. |
| **CompliAGL Anchor** | Proof and state hash anchoring, initially on Algorand. |
| **CompliAGL Graph** | Traceability across actor, policy, decision, execution, and proof. |
| **CompliAGL Network** | Future verification layer for auditors, regulators, and counterparties. |

---

## Architecture

```
AI Agent / Autonomous Actor
        ↓
DID / VC Identity
        ↓
Intent Object
        ↓
CompliAGL Core
        ↓
Decision:
  APPROVE  → continue
  DENY     → stop
  ESCALATE → Human Actor
        ↓
If APPROVED:
  Execution Adapter
        ↓
  x402 / API / Chain / Payment Rail
        ↓
  Settlement Layer, e.g. Solana, XRPL, Base, etc.
        ↓
  Execution Result
        ↓
AIProof
        ↓
Execution / Governance State Snapshot
        ↓
Anchoring Layer, e.g. Algorand
        ↓
Proof Graph
        ↓
Compliance Proof Network
```

---

## Chain-Agnostic Design

CompliAGL is infrastructure, not a bet on a single ecosystem.

- **CompliAGL does not depend on one blockchain.**
- **x402** can be one payment protocol.
- **Solana** can be one settlement layer.
- **Algorand** can be one anchoring layer.
- **XRPL, Base, Ethereum, Hedera, Canton,** and others can be added as future adapters.

The control plane stays constant; rails, settlement, and anchoring are pluggable.

---

## MVP Status

**Phase 1 — completed:**

- CompliAGL Core
- CompliAGL Execute
- CompliAGL Proof
- Frontend control plane

**Next phases:**

- CompliAGL Identity
- CompliAGL Anchor
- CompliAGL Graph
- CompliAGL Network

---

## Quick Start

**Backend**

```bash
git clone https://github.com/Compliledger/CompliAGL.git
cd CompliAGL/backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API will be available at **http://localhost:8000** and interactive docs at **http://localhost:8000/docs**.

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

The control plane UI will be available at **http://localhost:5173**.

---

## API Overview

The backend is a FastAPI service. Interactive Swagger documentation is always available at **`/docs`**.

**Governance & proof**

- `GET /health` — service health check.
- `POST /api/agents` · `GET /api/agents` — register and list actors/agents.
- `POST /api/policies` · `GET /api/policies` — manage governance policies.
- `POST /api/transactions` · `POST /api/transactions/{id}/evaluate` — submit and evaluate intents.
- `POST /api/approvals` — handle escalation approvals.
- `GET /api/audit` — browse the audit trail.
- `GET /api/proofs` — retrieve generated proof bundles.
- `GET /api/dashboard/summary` — control-plane summary metrics.

**Control plane (MVP 2)**

- `GET /api/mvp2/actors` · `GET /api/mvp2/policies` — actors and policies.
- `POST /api/mvp2/evaluate` — return a policy decision for an intent.
- `POST /api/mvp2/execute` — execute an approved action through an adapter.
- `POST /api/mvp2/proofs/generate` · `GET /api/mvp2/proofs` — generate and list AIProof bundles.

See `/docs` for full request/response schemas.

---

## Repository Structure

```
CompliAGL/
├── backend/            # FastAPI control-plane service
│   ├── app/            # Core, Execute, Proof, Identity, routes
│   ├── requirements.txt
│   ├── Procfile
│   └── railway.json
├── frontend/           # React + Vite control-plane UI
├── docs/               # Architecture and demo-flow documentation
├── Procfile            # Process definition for deployment
├── requirements.txt    # Root Python dependencies
├── README.md
└── LICENSE
```

---

## Deployment

CompliAGL deploys to **Railway**. The backend ships with a `Procfile` and `railway.json` (NIXPACKS builder) that start the FastAPI service via uvicorn, binding to the platform-provided `$PORT`.

---

## License

Released under the [MIT License](./LICENSE).
