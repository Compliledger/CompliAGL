# CompliAGL

> **The Agent Governance Layer for Open Wallets**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE)

Policy enforcement · Spend controls · Escalation workflows · Auditability · Proof generation

---

## What is CompliAGL?

**CompliAGL** (CompliLedger Agent Governance Layer) is a governance, policy, and proof system for autonomous agent wallets.

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

## Run Instructions

### Start the backend

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

## License

[MIT](./LICENSE) © CompliLedger

