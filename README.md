<p align="center">
  <h1 align="center">CompliAGL</h1>
  <p align="center"><b>The Agent Governance Layer for Open Wallets</b></p>
  <p align="center">
    Policy enforcement · Spend controls · Escalation workflows · Auditability · Proof generation
  </p>
</p>

---

CompliAGL adds a governance layer to agent wallets **before** any transaction executes. Every spend request is evaluated against configurable policies, producing a deterministic decision (`APPROVED`, `DENIED`, or `ESCALATED`) along with a cryptographic proof bundle for full auditability.

## Table of Contents

- [Quick Start](#quick-start)
- [Running the Services](#running-the-services)
- [Core Concepts](#core-concepts)
- [API Examples](#api-examples)
- [Smoke Test](#smoke-test)
- [Project Status](#project-status)
- [Repository Structure](#repository-structure)
- [License](#license)

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Compliledger/CompliAGL.git
cd CompliAGL

# 2. Install backend dependencies
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cd ..

# 3. Install frontend dependencies
cd frontend
npm install
cd ..

# 4. Run both services
#    Backend  → http://localhost:8000
#    Frontend → http://localhost:5173
make run
```

> **Tip:** You can also use `make install` to install everything in one step and then `make run` to launch both services.

---

## Running the Services

| Service | Command | URL |
|---------|---------|-----|
| **Backend** (FastAPI) | `make run-backend` | http://localhost:8000 |
| **Frontend** (Vite + React) | `make run-frontend` | http://localhost:5173 |
| **Both** | `make run` | — |

### Without Make

```bash
# Backend
cd backend && source venv/bin/activate && uvicorn app.main:app --reload --port 8000

# Frontend (in a separate terminal)
cd frontend && npm run dev
```

### All Makefile Targets

```
make help              # Show available targets
make install-backend   # Install backend dependencies
make install-frontend  # Install frontend dependencies
make install           # Install all dependencies
make run-backend       # Start backend on :8000
make run-frontend      # Start frontend on :5173
make run               # Start both services
```

---

## Core Concepts

| Concept | Description |
|---------|-------------|
| **Agent** | An autonomous software entity operating a wallet and initiating transactions on behalf of a user or organization. |
| **Policy** | A configurable rule set (spend limits, approval thresholds, blocklists) evaluated before any transaction is executed. |
| **Transaction** | A spend or transfer request submitted by an agent. CompliAGL intercepts it for policy evaluation before it reaches the chain. |
| **Decision** | The outcome of policy evaluation — one of **`APPROVED`**, **`DENIED`**, or **`ESCALATED`** — attached to every transaction. |
| **Proof Bundle** | A cryptographic attestation package that proves which policies were evaluated, what data was considered, and what decision was reached. |
| **Audit Log** | An immutable, append-only ledger of every decision and proof bundle, enabling compliance review and forensic analysis. |

---

## API Examples

> All examples assume the backend is running at `http://localhost:8000`.  
> Interactive Swagger docs are available at **http://localhost:8000/docs**.

### 1. Create an Agent

Register an autonomous agent that will submit transactions on behalf of your organization.

**Request**

```bash
curl -s -X POST http://localhost:8000/api/agents/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "treasury-bot",
    "description": "Autonomous treasury management agent",
    "wallet_address": "0xA1B2c3D4e5F6789012345678AbCdEf0123456789",
    "role": "agent"
  }'
```

**Response** `201 Created`

```json
{
  "id": "b3f1a2c4-5d6e-7f80-9a1b-2c3d4e5f6789",
  "name": "treasury-bot",
  "description": "Autonomous treasury management agent",
  "wallet_address": "0xA1B2c3D4e5F6789012345678AbCdEf0123456789",
  "status": "ACTIVE",
  "role": "agent",
  "created_at": "2026-04-03T14:00:00.000000",
  "updated_at": "2026-04-03T14:00:00.000000"
}
```

---

### 2. Create a Policy

Define a spend-limit policy that the decision engine will enforce before any transaction executes.

**Request**

```bash
curl -s -X POST http://localhost:8000/api/policies/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Per-Transaction Spend Cap",
    "description": "Deny any single transaction exceeding $10,000 USD",
    "policy_type": "SPEND_LIMIT",
    "parameters": {
      "max_amount": 10000,
      "currency": "USD"
    },
    "is_active": true
  }'
```

**Response** `201 Created`

```json
{
  "id": "c4d5e6f7-8a9b-0c1d-2e3f-4a5b6c7d8e9f",
  "name": "Per-Transaction Spend Cap",
  "description": "Deny any single transaction exceeding $10,000 USD",
  "policy_type": "SPEND_LIMIT",
  "parameters": {
    "max_amount": 10000,
    "currency": "USD"
  },
  "is_active": true,
  "created_at": "2026-04-03T14:01:00.000000",
  "updated_at": "2026-04-03T14:01:00.000000"
}
```

---

### 3. Submit a Transaction

Submit a spend request. The backend **creates** the transaction and **immediately evaluates** it against all active policies.

**Request**

```bash
curl -s -X POST http://localhost:8000/api/transactions/ \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "b3f1a2c4-5d6e-7f80-9a1b-2c3d4e5f6789",
    "recipient": "0x7890FeDcBa098765432112345678AbCdEf012345",
    "amount": 4500.00,
    "currency": "USD",
    "description": "Cloud compute — April invoice"
  }'
```

**Response** `201 Created`

```json
{
  "transaction_id": "d5e6f7a8-9b0c-1d2e-3f4a-5b6c7d8e9f00",
  "decision": "APPROVED",
  "results": [
    {
      "policy_id": "c4d5e6f7-8a9b-0c1d-2e3f-4a5b6c7d8e9f",
      "policy_type": "SPEND_LIMIT",
      "passed": true,
      "reason": "Amount $4,500.00 is within the $10,000 limit"
    }
  ],
  "proof_bundle_id": "e6f7a8b9-0c1d-2e3f-4a5b-6c7d8e9f0011"
}
```

---

### 4. Evaluate a Transaction (Escalated Example)

When a transaction falls in a gray area — for example, above an agent's individual authority but below the global cap — the decision engine returns `ESCALATED`.

**Request**

```bash
curl -s -X POST http://localhost:8000/api/transactions/ \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "b3f1a2c4-5d6e-7f80-9a1b-2c3d4e5f6789",
    "recipient": "0xDEADbeef00000000000000000000000000000000",
    "amount": 8500.00,
    "currency": "USD",
    "description": "Enterprise license — annual renewal"
  }'
```

**Response** `201 Created`

```json
{
  "transaction_id": "f7a8b9c0-1d2e-3f4a-5b6c-7d8e9f001122",
  "decision": "ESCALATED",
  "results": [
    {
      "policy_id": "c4d5e6f7-8a9b-0c1d-2e3f-4a5b6c7d8e9f",
      "policy_type": "SPEND_LIMIT",
      "passed": true,
      "reason": "Amount $8,500.00 is within the $10,000 limit"
    },
    {
      "policy_id": "a1b2c3d4-0000-1111-2222-333344445555",
      "policy_type": "APPROVAL_THRESHOLD",
      "passed": false,
      "reason": "Amount exceeds agent authority of $5,000 — escalation required"
    }
  ],
  "proof_bundle_id": "a8b9c0d1-2e3f-4a5b-6c7d-8e9f00112233"
}
```

---

### 5. View the Proof Bundle

Every decision produces a cryptographic proof bundle that records the policies evaluated, the data considered, and the decision reached.

**Request**

```bash
curl -s http://localhost:8000/api/proofs/?transaction_id=d5e6f7a8-9b0c-1d2e-3f4a-5b6c7d8e9f00
```

**Response** `200 OK`

```json
[
  {
    "id": "e6f7a8b9-0c1d-2e3f-4a5b-6c7d8e9f0011",
    "transaction_id": "d5e6f7a8-9b0c-1d2e-3f4a-5b6c7d8e9f00",
    "decision": "APPROVED",
    "policy_snapshot": [
      {
        "id": "c4d5e6f7-8a9b-0c1d-2e3f-4a5b6c7d8e9f",
        "name": "Per-Transaction Spend Cap",
        "policy_type": "SPEND_LIMIT",
        "parameters": { "max_amount": 10000, "currency": "USD" }
      }
    ],
    "evaluation_results": [
      { "passed": true, "reason": "Amount $4,500.00 is within the $10,000 limit" }
    ],
    "proof_hash": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "created_at": "2026-04-03T14:02:05.000000"
  }
]
```

---

### 6. Approve an Escalated Transaction

When a transaction is escalated, a human reviewer (or higher-authority agent) submits an approval decision.

**Request**

```bash
curl -s -X POST http://localhost:8000/api/approvals/ \
  -H "Content-Type: application/json" \
  -d '{
    "transaction_id": "f7a8b9c0-1d2e-3f4a-5b6c-7d8e9f001122",
    "reviewer_id": "human-reviewer-42",
    "action": "APPROVE",
    "comments": "Verified with finance — renewal is budgeted for Q2"
  }'
```

**Response** `201 Created`

```json
{
  "id": "b9c0d1e2-3f4a-5b6c-7d8e-9f0011223344",
  "transaction_id": "f7a8b9c0-1d2e-3f4a-5b6c-7d8e9f001122",
  "reviewer_id": "human-reviewer-42",
  "action": "APPROVE",
  "comments": "Verified with finance — renewal is budgeted for Q2",
  "created_at": "2026-04-03T14:10:00.000000"
}
```

---

### 7. Execute an Approved Transaction

After approval, fetch the transaction to confirm its status has been updated. Execution against the agent wallet can proceed once the status is `APPROVED`.

**Request**

```bash
curl -s http://localhost:8000/api/transactions/f7a8b9c0-1d2e-3f4a-5b6c-7d8e9f001122
```

**Response** `200 OK`

```json
{
  "id": "f7a8b9c0-1d2e-3f4a-5b6c-7d8e9f001122",
  "agent_id": "b3f1a2c4-5d6e-7f80-9a1b-2c3d4e5f6789",
  "recipient": "0xDEADbeef00000000000000000000000000000000",
  "amount": 8500.00,
  "currency": "USD",
  "description": "Enterprise license — annual renewal",
  "status": "APPROVED",
  "created_at": "2026-04-03T14:05:00.000000",
  "updated_at": "2026-04-03T14:10:00.000000"
}
```

---

### 8. View Dashboard Summary

Use the listing endpoints to build a governance dashboard view — agents, recent transactions, and audit trail.

**Agents**

```bash
curl -s http://localhost:8000/api/agents/
```

**Recent Transactions**

```bash
curl -s http://localhost:8000/api/transactions/?limit=10
```

**Audit Log**

```bash
curl -s http://localhost:8000/api/audit/?limit=10
```

**Example Audit Entry**

```json
{
  "id": "c0d1e2f3-4a5b-6c7d-8e9f-001122334455",
  "entity_type": "transaction",
  "entity_id": "d5e6f7a8-9b0c-1d2e-3f4a-5b6c7d8e9f00",
  "action": "EVALUATED:APPROVED",
  "details": "{\"results\": [{\"passed\": true}], \"proof_id\": \"e6f7a8b9-0c1d-2e3f-4a5b-6c7d8e9f0011\"}",
  "performed_by": "system",
  "created_at": "2026-04-03T14:02:05.000000"
}
```

---

## Smoke Test

A minimal end-to-end curl flow you can run against a local instance to verify the governance pipeline works.

> **Prerequisites:** The backend must be running on `http://localhost:8000`.  
> Start it with: `cd backend && uvicorn app.main:app --reload --port 8000`

```bash
#!/usr/bin/env bash
# CompliAGL Smoke Test
# Exercises: agent → policy → transaction → evaluation → approval → execution
set -euo pipefail
BASE="http://localhost:8000"

echo "=== 1. Create Agent ==="
AGENT=$(curl -sf -X POST "$BASE/api/agents/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "smoke-test-agent",
    "description": "Agent created by smoke test",
    "wallet_address": "0xSmoke1234567890abcdef1234567890abcdef00",
    "role": "agent"
  }')
AGENT_ID=$(echo "$AGENT" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Agent ID: $AGENT_ID"

echo ""
echo "=== 2. Create Policy ==="
POLICY=$(curl -sf -X POST "$BASE/api/policies/" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Smoke Test Spend Limit",
    "description": "Cap single transactions at $5,000",
    "policy_type": "SPEND_LIMIT",
    "parameters": { "max_amount": 5000, "currency": "USD" },
    "is_active": true
  }')
POLICY_ID=$(echo "$POLICY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
echo "Policy ID: $POLICY_ID"

echo ""
echo "=== 3. Submit Transaction (should be APPROVED) ==="
EVAL=$(curl -sf -X POST "$BASE/api/transactions/" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"recipient\": \"0xRecipientAddress000000000000000000000000\",
    \"amount\": 1500.00,
    \"currency\": \"USD\",
    \"description\": \"Smoke-test approved transaction\"
  }")
DECISION=$(echo "$EVAL" | python3 -c "import sys,json; print(json.load(sys.stdin)['decision'])")
TX_ID=$(echo "$EVAL" | python3 -c "import sys,json; print(json.load(sys.stdin)['transaction_id'])")
echo "Transaction ID: $TX_ID"
echo "Decision: $DECISION"

echo ""
echo "=== 4. Verify Proof Bundle ==="
curl -sf "$BASE/api/proofs/?transaction_id=$TX_ID" | python3 -m json.tool

echo ""
echo "=== 5. Submit Escalated Transaction ==="
EVAL2=$(curl -sf -X POST "$BASE/api/transactions/" \
  -H "Content-Type: application/json" \
  -d "{
    \"agent_id\": \"$AGENT_ID\",
    \"recipient\": \"0xRecipientAddress000000000000000000000000\",
    \"amount\": 7500.00,
    \"currency\": \"USD\",
    \"description\": \"Smoke-test escalated transaction\"
  }")
DECISION2=$(echo "$EVAL2" | python3 -c "import sys,json; print(json.load(sys.stdin)['decision'])")
TX_ID2=$(echo "$EVAL2" | python3 -c "import sys,json; print(json.load(sys.stdin)['transaction_id'])")
echo "Transaction ID: $TX_ID2"
echo "Decision: $DECISION2"

echo ""
echo "=== 6. Approve Escalated Transaction ==="
if [ "$DECISION2" = "ESCALATED" ]; then
  APPROVAL=$(curl -sf -X POST "$BASE/api/approvals/" \
    -H "Content-Type: application/json" \
    -d "{
      \"transaction_id\": \"$TX_ID2\",
      \"reviewer_id\": \"smoke-test-reviewer\",
      \"action\": \"APPROVE\",
      \"comments\": \"Approved during smoke test\"
    }")
  echo "$APPROVAL" | python3 -m json.tool
else
  echo "Transaction was not escalated (decision: $DECISION2) — skipping approval."
fi

echo ""
echo "=== 7. Verify Final Transaction State ==="
curl -sf "$BASE/api/transactions/$TX_ID2" | python3 -m json.tool

echo ""
echo "=== Smoke test complete ==="
```

**Expected flow:**

| Step | Action | Expected Decision |
|------|--------|-------------------|
| 1 | Create agent | `ACTIVE` agent returned |
| 2 | Create policy (spend limit $5,000) | Policy stored |
| 3 | Submit $1,500 transaction | `APPROVED` |
| 4 | Verify proof bundle | Proof with `sha256` hash |
| 5 | Submit $7,500 transaction | `ESCALATED` or `DENIED` |
| 6 | Approve if escalated | Approval recorded |
| 7 | Check transaction status | `APPROVED` or `DENIED` |

---

## Project Status

> 🚧 **MVP in progress — Hackathon build**

The current focus areas are:

- ✅ Policy enforcement engine
- ✅ Decision service (`APPROVED` / `DENIED` / `ESCALATED`)
- ✅ Proof bundle generation
- 🔄 Frontend governance dashboard
- 🔄 Audit log persistence & search
- 📋 Agent registration & wallet linking

---

## Repository Structure

```
CompliAGL/
├── backend/          # FastAPI service — policy engine, decisions, proofs
│   └── README.md
├── frontend/         # React + Vite dashboard — governance UI
│   └── README.md
├── Makefile          # Dev commands (install, run, etc.)
└── README.md         # ← You are here
```

See [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md) for service-specific details.

# CompliAGL — Agent Governance Layer

**AI agents can already transact on your behalf — but who's watching the agents?**

Today's autonomous agents negotiate deals, sign contracts, and move money. But they operate without guardrails. There are no spend limits, no approval workflows, no audit trails, and no way for an enterprise to prove that a transaction was compliant *before* it executed. CompliAGL is the governance layer that fixes this. It sits between agent intent and wallet execution, enforcing policies, generating compliance proofs, and ensuring every autonomous transaction is controlled, auditable, and trustworthy.

---

## 🔍 Why This Matters

Autonomous commerce is here — agents are buying cloud resources, executing trades, and managing supply chains in real time. But without governance:

- **Enterprises can't adopt agent wallets** — regulated industries require policy enforcement and auditability before they can trust an agent with real money.
- **Compliance must happen *before* execution, not after** — post-hoc audits don't prevent bad transactions; they just find them too late.
- **Autonomous commerce needs controls** — spending limits, multi-party approvals, and escalation workflows are not optional for real-world deployment.

CompliAGL makes agent-driven transactions enterprise-ready by embedding compliance directly into the transaction lifecycle.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| **Policy Enforcement** | Define and enforce spend limits, allowlists, blocklists, and custom rules — evaluated before every transaction. |
| **Decision Engine** | A rules engine that evaluates each transaction against the active policy set and returns an allow / deny / escalate decision in milliseconds. |
| **Escalation Workflows** | When a transaction exceeds policy thresholds, it's automatically routed to a human approver or a higher-authority agent — no silent failures. |
| **Proof Generation** | Every decision produces a cryptographic compliance proof that can be independently verified, anchored on-chain, or attached to the transaction. |
| **Audit Logging** | Immutable, structured logs capture the full decision context — who requested, what policy applied, what was decided, and why. |

---

## 🎬 Demo Scenarios

### ✅ Approved Transaction
> An agent requests a \$50 cloud compute purchase. The policy engine evaluates: amount is under the \$500 daily limit, vendor is on the allowlist, and the agent role has the required permission. **Result:** Transaction is approved instantly with a compliance proof attached.

### ❌ Denied Transaction
> An agent attempts a \$10,000 transfer to an unknown wallet. The policy engine flags: amount exceeds the per-transaction cap, recipient is not on the allowlist. **Result:** Transaction is denied, the agent receives a structured rejection reason, and the event is logged for audit.

### ⏫ Escalated Transaction
> An agent requests a \$2,500 software license purchase — within the global cap but above the agent's individual authority. The decision engine escalates the request to a human treasury approver. **Result:** The approver reviews and confirms; the transaction proceeds with dual-signature proof.

---

## 🚀 Future Vision

CompliAGL is designed to grow with the ecosystem:

- **OWS Integration** — Native support for the Open Wallet Standard, enabling plug-and-play governance for any OWS-compatible agent wallet.
- **x402 Payment Protocol** — Built-in compliance for HTTP 402-based micropayments, so agents can pay for APIs and services with policy enforcement baked in.
- **Blockchain Anchoring** — Anchor compliance proofs on-chain (Ethereum, Solana, or any EVM chain) for tamper-proof, publicly verifiable audit trails.
- **ZK Identity** — Zero-knowledge proof-based identity verification — agents can prove they are authorized without revealing sensitive organizational data.

---

## 📄 License

This project is licensed under the terms of the [MIT License](LICENSE).

---

<p align="center">
  <strong>CompliAGL</strong> — Because autonomous agents need governance too.
</p>
> **OWS gives agents wallets. CompliAGL governs what those wallets are allowed to do.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

---

## Overview

**CompliAGL** (CompliLedger Agent Governance Layer) is a governance, policy, and proof system for agent wallets built on top of the [Open Wallet Standard (OWS)](https://openwalletfoundation.org/).

As autonomous AI agents gain the ability to hold and spend digital assets, a critical gap emerges: **who governs what an agent is allowed to do?** CompliAGL fills that gap by sitting between an agent's intent and its wallet execution — enforcing policy, generating cryptographic proof, and escalating when human oversight is required.

---

## Problem

Modern AI agents can be granted wallets via the Open Wallet Standard. But giving an agent a wallet without governance is like giving a contractor a corporate credit card with no spending policy:

- Agents may execute transactions that exceed limits or violate rules.
- There is no auditable proof that a policy was checked before execution.
- Escalation paths for edge cases don't exist.
- Compliance and accountability are undefined.

Without a governance layer, agent wallets are powerful but ungoverned.

---

## Solution

CompliAGL introduces a **pre-execution governance checkpoint** for every agent wallet action:

1. **Policy Engine** — defines rules (spend limits, allowed recipients, time windows, asset types).
2. **Decision Engine** — evaluates each proposed transaction against active policies.
3. **Proof Engine** — generates a cryptographic proof-of-compliance (or denial) for every decision.
4. **Escalation Engine** — routes edge cases to human reviewers before execution proceeds.

Every transaction either gets a **green light with proof**, a **hard denial**, or an **escalation to a human approver** — nothing slips through ungoverned.

---

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│  Agent dashboard · Policy manager · Audit log viewer │
└───────────────────────────┬─────────────────────────┘
                            │ REST / WebSocket
┌───────────────────────────▼─────────────────────────┐
│                   Backend (FastAPI)                  │
│         API gateway · Auth · Session management      │
└───────────────────────────┬─────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────┐
│               CompliAGL Governance Layer             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │Policy Engine│  │Decision Eng. │  │Proof Engine│  │
│  └─────────────┘  └──────────────┘  └────────────┘  │
│                    ┌──────────────┐                  │
│                    │  Escalation  │                  │
│                    │    Engine    │                  │
│                    └──────────────┘                  │
└───────────────────────────┬─────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────┐
│              Agent Wallet (OWS-compliant)            │
│         Transaction execution · Asset custody        │
└─────────────────────────────────────────────────────┘
```

See [`docs/architecture.md`](./docs/architecture.md) for full details.

---

## Demo Flow

CompliAGL demonstrates three core governance outcomes:

| Scenario | Trigger | Outcome |
|---|---|---|
| ✅ **Approved** | Transaction is within policy limits | Proof generated, wallet executes |
| ❌ **Denied** | Transaction violates a policy rule | Denial proof recorded, wallet blocked |
| ⏸ **Escalated** | Transaction is in a gray area | Routed to human approver; wallet paused |

See [`docs/demo-flow.md`](./docs/demo-flow.md) for detailed scenarios and expected outputs.

---

## How to Run Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- (Optional) Docker

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

The API will be available at `http://localhost:8000`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The UI will be available at `http://localhost:5173`.

### Environment Variables

Copy `.env.example` to `.env` in each directory and fill in the required values before starting.

---

## Hackathon Context — OWS

This project was built for a hackathon centered on the **Open Wallet Standard (OWS)**, an open framework for interoperable digital wallets across agents, humans, and institutions.

**CompliAGL's role in the OWS ecosystem:**

- OWS defines _how_ an agent holds and transfers assets.
- CompliAGL defines _whether_ an agent is _allowed_ to hold and transfer those assets.
- Together they form a complete, governed, auditable agent wallet stack.

**Future integration points:**

- Native OWS wallet adapter for real-time policy gating
- x402 payment protocol support for governed micro-payments
- On-chain proof anchoring for immutable audit trails
- DAO-based policy governance for decentralized rule management

---

## Project Structure

```
compliagl/
├── README.md
├── LICENSE
├── .gitignore
├── docs/
│   ├── architecture.md    # System design and component details
│   └── demo-flow.md       # Demo scenarios and expected outcomes
├── backend/               # FastAPI governance API
└── frontend/              # React dashboard
```

---

## License

This project is licensed under the terms specified in the repository. See [LICENSE](LICENSE) for details.
[MIT](./LICENSE) © CompliLedger

