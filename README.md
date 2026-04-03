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

[MIT](./LICENSE) © CompliLedger

