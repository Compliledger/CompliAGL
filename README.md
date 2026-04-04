# CompliAGL

> **The Agent Governance Layer for Open Wallets**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

Policy enforcement · Spend controls · Escalation workflows · Auditability · Proof generation
- [Quick Start](#quick-start)
- [Running the Services](#running-the-services)
- [Core Concepts](#core-concepts)
- [API Examples](#api-examples)
- [Smoke Test](#smoke-test)
- [Project Status](#project-status)
- [Repository Structure](#repository-structure)
- [Deploying to Railway](#deploying-to-railway)
- [License](#license)

---

## What is CompliAGL?

**CompliAGL** (CompliLedger Agent Governance Layer) is a governance, policy, and proof system for autonomous agent wallets.

# 2. Create a virtual environment and install root dependencies
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Install backend dependencies
cd backend
pip install -r requirements.txt
cd ..

# 4. Install frontend dependencies
cd frontend
npm install
cd ..

# 5. Initialise the database and seed demo data
python -m app.db.init_db

# 6. Run both services
#    Backend  → http://localhost:8000
#    Frontend → http://localhost:5173
make run
As AI agents gain the ability to hold and spend digital assets, a critical gap emerges: **who governs what an agent is allowed to do?** CompliAGL fills that gap by sitting between an agent's intent and its wallet execution — enforcing policies, generating cryptographic compliance proofs, and escalating when human oversight is required.

Every spend request is evaluated against configurable policies, producing a deterministic decision (`APPROVED`, `DENIED`, or `ESCALATED`) along with a cryptographic proof bundle for full auditability.

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React)                  │
│  Agent dashboard · Policy manager · Audit log viewer │
└───────────────────────────┬─────────────────────────┘
                            │ REST API
┌───────────────────────────▼─────────────────────────┐
│                   Backend (FastAPI)                  │
│         API gateway · CORS · Lifespan hooks          │
├─────────────────────────────────────────────────────┤
│               CompliAGL Governance Layer             │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │Policy Engine│  │Decision Eng. │  │Proof Engine│  │
│  └─────────────┘  └──────────────┘  └────────────┘  │
│                    ┌──────────────┐                  │
│                    │  Escalation  │                  │
│                    │    Engine    │                  │
│                    └──────────────┘                  │
├─────────────────────────────────────────────────────┤
│           SQLAlchemy 2.0 + SQLite (local dev)        │
└─────────────────────────────────────────────────────┘
```

**Tech stack:** Python 3.11+ · FastAPI · Pydantic v2 · SQLAlchemy 2.0 · SQLite · uvicorn

---

## Folder Structure
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

## Database & Seed Data

CompliAGL uses SQLite by default. A single command creates all tables and
optionally seeds demo data so you can start exploring immediately.

```bash
# Create tables + insert demo seed data (default)
python -m app.db.init_db

# Create tables only — no seed data
python -m app.db.init_db --no-seed

# Use a custom database URL
python -m app.db.init_db --db-url sqlite:///./my_dev.db
```

The seed data includes:

| Agent | Wallet | Per-Tx Limit | Allowed Vendors | Chains |
|---|---|---|---|---|
| **TravelAgent-01** | `agent_wallet_travel_001` | $450 | airline_api, hotel_api, restaurant_api | xrpl, base, ethereum |
| **ResearchAgent-01** | `agent_wallet_research_001` | $50 | firecrawl, news_api, research_api | base, ethereum |

Plus four example transactions (approved, denied, escalated), decisions, proof
records, and audit-log entries.

> **Re-running is safe** — the seed function is idempotent and will skip if
> data already exists.

---

## Core Concepts
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
CompliAGL/
├── app/              # Shared models, schemas, enums, and DB utilities
│   ├── db/
│   │   └── init_db.py  # DB init & seed (python -m app.db.init_db)
│   ├── models/
│   ├── schemas/
│   └── utils/
├── backend/          # FastAPI service — policy engine, decisions, proofs
│   └── README.md
├── frontend/         # React + Vite dashboard — governance UI
│   └── README.md
├── Makefile          # Dev commands (install, run, etc.)
└── README.md         # ← You are here

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
├── README.md                  # ← You are here
├── requirements.txt           # Root-level Python dependencies
├── .env.example               # Example environment variables
├── Makefile                   # Dev commands (install, run)
├── LICENSE
├── docs/
│   ├── architecture.md        # System design details
│   └── demo-flow.md           # Demo scenarios and expected outcomes
├── app/                       # Shared models, schemas, enums (used by root tests)
│   ├── models/
│   │   └── models.py
│   ├── schemas/
│   │   └── schemas.py
│   └── utils/
│       └── enums.py           # Single source of truth for business enums
├── backend/                   # FastAPI service
│   ├── app/
│   │   ├── main.py            # FastAPI app entry point + router registration
│   │   ├── api/routes/        # HTTP route handlers
│   │   │   ├── health.py      #   GET  /health
│   │   │   ├── agents.py      #   CRUD /api/agents
│   │   │   ├── policies.py    #   CRUD /api/policies
│   │   │   ├── transactions.py#   POST /api/transactions (create + evaluate)
│   │   │   ├── approvals.py   #   CRUD /api/approvals
│   │   │   ├── audit.py       #   GET  /api/audit
│   │   │   └── proofs.py      #   GET  /api/proofs
│   │   ├── core/
│   │   │   ├── config.py      # Settings from env vars (pydantic-settings)
│   │   │   ├── database.py    # SQLAlchemy engine + session factory
│   │   │   └── security.py    # Auth helpers (placeholder)
│   │   ├── models/            # SQLAlchemy ORM models
│   │   ├── schemas/           # Pydantic request/response schemas
│   │   ├── services/          # Business logic layer
│   │   │   ├── evaluation_service.py  # Orchestrates rule engine + proof + audit
│   │   │   ├── policy_service.py
│   │   │   ├── agent_service.py
│   │   │   ├── approval_service.py
│   │   │   ├── audit_service.py
│   │   │   └── proof_service.py
│   │   ├── utils/             # Hashing, timestamps, enums, rule engine
│   │   └── db/
│   │       └── init_db.py     # Table creation on startup
│   ├── requirements.txt       # Backend-specific pinned dependencies
│   ├── .env.example
│   └── README.md
├── frontend/                  # React + Vite governance dashboard
│   └── README.md
└── tests/                     # Root-level tests (enums, shared logic)
    └── test_enums.py
```

---

## Setup Instructions

### Prerequisites

- Python 3.11+
- Node.js 18+ (for the frontend)
- Git

### 1. Clone the repository

```bash
git clone https://github.com/Compliledger/CompliAGL.git
cd CompliAGL
```

### 2. Create a virtual environment and install dependencies

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. Configure environment variables

```bash
cp .env.example .env
# Edit .env if you need to change any defaults
```

The default `.env.example` contains:

```
APP_NAME=CompliAGL Backend
APP_VERSION=0.1.0
DEBUG=true
DATABASE_URL=sqlite:///./compliagl.db
```

### 4. (Optional) Install frontend

```bash
cd ../frontend
npm install
```

> **Tip:** You can also use `make install` from the repo root to install both backend and frontend dependencies in one step.

---

### Install
## Run Instructions

### Start the backend

```bash
# Root-level dependencies (shared models, schemas, enums)
pip install -r requirements.txt

# Backend dependencies
cd backend
pip install -r requirements.txt
cd ..
```

### Seed the Database

```bash
python -m app.db.init_db            # tables + demo data
python -m app.db.init_db --no-seed  # tables only
```

### Backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8000
```

The API will be available at **http://localhost:8000**.
Interactive Swagger docs at **http://localhost:8000/docs**.

### Start the frontend (separate terminal)

```bash
cd frontend
npm run dev
```

The UI will be available at **http://localhost:5173**.

### Using Make

```bash
make install           # Install all dependencies (backend + frontend)
make run-backend       # Start backend on :8000
make run-frontend      # Start frontend on :5173
make run               # Start both services
```

---

## Seed Instructions

There is no dedicated seed script yet. To populate the database with sample data, use the API directly after starting the backend:

### 1. Register an agent

```bash
curl -X POST http://localhost:8000/api/agents/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "procurement-bot",
    "role": "purchaser",
    "wallet_address": "0xABCDEF1234567890"
  }'
```

### 2. Create a policy

```bash
curl -X POST http://localhost:8000/api/policies/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Spend Limit - $500",
    "policy_type": "SPEND_LIMIT",
    "rules": {"max_amount": 500, "currency": "USD"},
    "is_active": true
  }'
```

### 3. Submit a transaction (triggers evaluation)

```bash
curl -X POST http://localhost:8000/api/transactions/ \
  -H "Content-Type: application/json" \
  -d '{
    "agent_id": "<agent-id-from-step-1>",
    "recipient": "vendor-cloud-co",
    "amount": 50.00,
    "currency": "USD"
  }'
```

> The transaction endpoint automatically evaluates the transaction against all active policies and returns the decision.

---

## Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | App info (name, version, docs link) |
| `GET` | `/health` | Health check |
| `POST` | `/api/agents/` | Register an agent |
| `GET` | `/api/agents/` | List agents |
| `GET` | `/api/agents/{id}` | Get agent by ID |
| `PATCH` | `/api/agents/{id}` | Update agent |
| `DELETE` | `/api/agents/{id}` | Delete agent |
| `POST` | `/api/policies/` | Create a policy |
| `GET` | `/api/policies/` | List policies |
| `GET` | `/api/policies/{id}` | Get policy by ID |
| `PATCH` | `/api/policies/{id}` | Update policy |
| `DELETE` | `/api/policies/{id}` | Delete policy |
| `POST` | `/api/transactions/` | Submit & evaluate a transaction |
| `GET` | `/api/transactions/` | List transactions |
| `GET` | `/api/transactions/{id}` | Get transaction by ID |
| `POST` | `/api/approvals/` | Submit an approval decision |
| `GET` | `/api/approvals/` | List approvals |
| `GET` | `/api/audit/` | List audit log entries |
| `GET` | `/api/proofs/` | List proof bundles |

---

## Example Transaction Evaluation Flow

Below is the end-to-end flow when an agent submits a transaction:

```
Agent submits POST /api/transactions/
        │
        ▼
┌─────────────────────┐
│  Transaction created │  (persisted with PENDING status)
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Evaluation Service  │  Fetches all active policies
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│    Rule Engine       │  Evaluates transaction context against each policy
│                      │  (amount, recipient, currency, agent role)
└─────────┬───────────┘
          │
          ├── All policies pass    → Decision: APPROVED
          ├── Any policy fails     → Decision: DENIED
          └── Escalation triggered → Decision: ESCALATED
          │
          ▼
┌─────────────────────┐
│  Transaction status  │  Updated to APPROVED / DENIED / ESCALATED
│  updated in DB       │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Proof Bundle        │  Cryptographic proof created with:
│  generated           │  - Policy snapshot at time of evaluation
│                      │  - Evaluation results per policy
│                      │  - Final decision
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Audit Log entry     │  Immutable record: entity, action, details, timestamp
│  created             │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│  Response returned   │  { transaction_id, decision, results, proof_bundle_id }
└─────────────────────┘
```

### Example response

```json
{
  "transaction_id": "a1b2c3d4-...",
  "decision": "APPROVED",
  "results": [
    {
      "policy": "Spend Limit - $500",
      "result": "PASS",
      "reason": "Amount 50.00 is within limit of 500"
    }
  ],
  "proof_bundle_id": "e5f6g7h8-..."
}
```

If the transaction is **ESCALATED**, a human approver can review it via `POST /api/approvals/` and the transaction will be re-evaluated or finalized.

---

## Notes on Future OWS / x402 Integration

CompliAGL is designed to integrate with the broader agent wallet ecosystem:

### Open Wallet Standard (OWS)

- **Native OWS wallet adapter** — CompliAGL will act as a middleware layer between OWS-compatible agent wallets and the blockchain, intercepting every transaction for policy evaluation before execution.
- **Standardized governance interface** — Any wallet implementing OWS will be able to plug in CompliAGL as its governance layer without custom integration work.
- **Multi-chain support** — The governance layer is chain-agnostic; OWS integration will enable enforcement across Ethereum, Solana, and other supported networks.

### x402 Payment Protocol

- **HTTP 402 micropayment compliance** — When agents pay for APIs or services via the x402 protocol, CompliAGL will enforce spend policies on each micropayment before it is authorized.
- **Per-request policy evaluation** — Each x402 payment request will pass through the policy engine, enabling fine-grained controls like per-API spend caps, rate-limited payments, and vendor allowlists.
- **Proof-of-compliance headers** — CompliAGL will attach cryptographic proof headers to x402 responses, allowing service providers to verify that the agent's payment was governance-approved.

### Blockchain Anchoring

- **On-chain proof anchoring** — Proof bundles will be anchored on-chain (Ethereum, Solana, or any EVM chain) for tamper-proof, publicly verifiable audit trails.
- **Zero-knowledge identity** — Agents will be able to prove they are authorized without revealing sensitive organizational data.

---

## Deploying to Railway

The backend is ready for one-click deployment on [Railway](https://railway.app).

### 1. Deploy from GitHub

1. Log in to [railway.app](https://railway.app) and click **New Project → Deploy from GitHub repo**.
2. Select the `CompliAGL` repository and choose the **`backend/`** directory as the root (Railway supports subdirectory deployments via the service settings).
3. Railway will detect the `Procfile` / `railway.json` and use:
   ```
   uvicorn app.main:app --host 0.0.0.0 --port $PORT
   ```

### 2. Set Environment Variables

In the Railway dashboard → **Variables**, add the following:

| Variable | Example value | Notes |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./compliagl.db` | Use a persistent volume or Postgres URL for production |
| `SECRET_KEY` | *(generate a random string)* | Required — never use the default |
| `APP_NAME` | `CompliAGL` | Optional, defaults to `CompliAGL` |
| `APP_VERSION` | `0.1.0` | Optional |
| `DEBUG` | `false` | Set to `false` in production |

> `PORT` is injected automatically by Railway — do **not** set it manually.

### 3. Generate a Public Domain

1. In the Railway dashboard, open your service and click **Settings → Networking**.
2. Click **Generate Domain** to get a public `*.up.railway.app` URL.
3. The API docs will be available at `https://<your-domain>.up.railway.app/docs`.

---

## License

[MIT](./LICENSE) © CompliLedger

