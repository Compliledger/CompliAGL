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
| Database | PostgreSQL (via SQLAlchemy / Alembic) |
| Task Queue | Celery + Redis (planned) |

## Getting Started

```bash
cd backend
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API will be available at **http://localhost:8000**.

> **Note:** This service is under active development as part of the MVP / hackathon build. APIs and schemas may change.
