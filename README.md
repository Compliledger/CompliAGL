# CompliAGL — Agent Governance Layer

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

[MIT](./LICENSE) © CompliLedger

