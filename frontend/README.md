# CompliAGL — Frontend (Compli402 Demo Dashboard)

## Overview

A **minimal React + Vite** dashboard that visualises the end-to-end
**Compli402** governed-execution flow for the Global x402 Challenge demo:

```
Actor → Intent → Policy Decision → x402 Payment → Execution → AIProof → Algorand Anchor
```

The dashboard renders one panel per stage:

- **Actor** — the acting entity (resolved actor identity).
- **Intent** — the action, amount, and currency being requested.
- **Policy Decision** — `APPROVED`, `DENIED`, or `ESCALATION_REQUIRED` with reason codes.
- **x402 Payment Status** — payment required / verified, reference, facilitator, network.
- **Execution Result** — the executed action and its execution reference.
- **AIProof Bundle** — the full, deterministically-hashed AIProof record.
- **Algorand Anchor Receipt** — the anchor transaction id and explorer link.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | React 18 |
| Build Tool | Vite |
| HTTP Client | `fetch` |

## Configuration

The backend base URL is provided via the `VITE_API_BASE_URL` environment
variable. Copy the example file and adjust as needed:

```bash
cp .env.example .env
# .env
# VITE_API_BASE_URL=http://localhost:8000
```

## Backend Endpoints Used

| Endpoint | Purpose |
|----------|---------|
| `GET /api/compli402/health` | Service health + x402 configuration. |
| `POST /api/compli402/verify/intent` | Evaluate an intent against governance policy. |
| `POST /api/compli402/execute` | Run the full governance → payment → execute → anchor flow. |
| `GET /api/compli402/proofs/latest` | Fetch the most recent AIProof bundle. |

## Getting Started

```bash
cd frontend
npm install
npm run dev
```

The app will be available at **http://localhost:5173**.

To produce a production build:

```bash
npm run build
npm run preview
```

> **Note:** This is a demo surface built for the x402 Challenge. The backend
> uses an in-memory store and a mock x402 facilitator by default, so the full
> flow runs locally without external services or secrets.
