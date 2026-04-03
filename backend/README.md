# CompliAGL — Backend

## Overview

The CompliAGL backend is a **Python / FastAPI** service that powers the Agent Governance Layer. It is responsible for:

- **Policy Engine** — Evaluates spend-control rules, approval thresholds, and escalation triggers before any agent-initiated transaction is executed.
- **Decision Service** — Returns a deterministic verdict (`APPROVED`, `DENIED`, or `ESCALATED`) for every transaction request.
- **Proof Generation** — Produces cryptographic proof bundles that attest to the policy evaluation, enabling verifiable auditability.
- **Audit Log** — Persists an immutable, append-only record of every decision for compliance and forensic review.
- **REST API** — Exposes endpoints consumed by the frontend dashboard and by external agent wallets.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | FastAPI |
| Language | Python 3.11+ |
| Validation | Pydantic v2 |
| ORM | SQLAlchemy 2.0 |
| Database | SQLite (local dev) |
| Server | uvicorn |

## Getting Started

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt

# (Optional) copy and edit the env file
cp .env.example .env

# Start the server
uvicorn app.main:app --reload --port 8000
```

The API will be available at **http://localhost:8000**.
Interactive docs (Swagger UI) at **http://localhost:8000/docs**.

## Project Layout

```
backend/
├── app/
│   ├── main.py                  # FastAPI app init + router registration
│   ├── api/routes/              # HTTP route handlers
│   │   ├── health.py            # GET /health
│   │   ├── agents.py            # CRUD /api/agents
│   │   ├── policies.py          # CRUD /api/policies
│   │   ├── transactions.py      # POST /api/transactions (create + evaluate)
│   │   ├── approvals.py         # CRUD /api/approvals
│   │   ├── audit.py             # GET  /api/audit
│   │   └── proofs.py            # GET  /api/proofs
│   ├── core/
│   │   ├── config.py            # Settings from env vars
│   │   ├── database.py          # SQLAlchemy engine + session
│   │   └── security.py          # Auth helpers (placeholder)
│   ├── models/                  # SQLAlchemy ORM models
│   ├── schemas/                 # Pydantic request/response schemas
│   ├── services/                # Business logic layer
│   ├── utils/                   # Hashing, timestamps, enums, rule engine
│   └── db/
│       └── init_db.py           # Table creation on startup
├── requirements.txt
├── .env.example
└── README.md
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | App info |
| GET | `/health` | Health check |
| POST | `/api/agents/` | Register an agent |
| GET | `/api/agents/` | List agents |
| GET | `/api/agents/{id}` | Get agent |
| PATCH | `/api/agents/{id}` | Update agent |
| DELETE | `/api/agents/{id}` | Delete agent |
| POST | `/api/policies/` | Create a policy |
| GET | `/api/policies/` | List policies |
| GET | `/api/policies/{id}` | Get policy |
| PATCH | `/api/policies/{id}` | Update policy |
| DELETE | `/api/policies/{id}` | Delete policy |
| POST | `/api/transactions/` | Submit & evaluate a transaction |
| GET | `/api/transactions/` | List transactions |
| GET | `/api/transactions/{id}` | Get transaction |
| POST | `/api/approvals/` | Submit an approval decision |
| GET | `/api/approvals/` | List approvals |
| GET | `/api/audit/` | List audit log entries |
| GET | `/api/proofs/` | List proof bundles |

> **Note:** This service is under active development as part of the MVP / hackathon build. APIs and schemas may change.
