# Architecture

## Overview

CompliAGL is structured as a full-stack web application with a dedicated governance layer sitting between the API and the agent wallet. Every agent wallet action passes through the governance layer before execution is permitted.

---

## Component Diagram

```
┌──────────────────────────────────────────────────────────────┐
│                       Frontend (React)                        │
│                                                              │
│  ┌──────────────────┐  ┌─────────────────┐  ┌────────────┐  │
│  │  Agent Dashboard │  │  Policy Manager │  │ Audit Log  │  │
│  └──────────────────┘  └─────────────────┘  └────────────┘  │
└───────────────────────────────┬──────────────────────────────┘
                                │ HTTP REST / WebSocket
┌───────────────────────────────▼──────────────────────────────┐
│                       Backend (FastAPI)                       │
│                                                              │
│  ┌────────────────┐  ┌────────────────┐  ┌───────────────┐   │
│  │  API Gateway   │  │     Auth       │  │   Sessions    │   │
│  └────────────────┘  └────────────────┘  └───────────────┘   │
└───────────────────────────────┬──────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────┐
│                  CompliAGL Governance Layer                   │
│                                                              │
│  ┌─────────────────┐   ┌──────────────────┐                  │
│  │  Policy Engine  │   │  Decision Engine  │                  │
│  │                 │   │                  │                  │
│  │ • Spend limits  │   │ • Rule evaluator │                  │
│  │ • Asset types   │   │ • Allow / Deny   │                  │
│  │ • Time windows  │   │ • Escalate path  │                  │
│  │ • Recipients    │   │                  │                  │
│  └─────────────────┘   └──────────────────┘                  │
│                                                              │
│  ┌─────────────────┐   ┌──────────────────┐                  │
│  │  Proof Engine   │   │ Escalation Engine │                  │
│  │                 │   │                  │                  │
│  │ • Decision hash │   │ • Human review   │                  │
│  │ • Timestamped   │   │ • Notification   │                  │
│  │ • Signed record │   │ • Approve/Deny   │                  │
│  └─────────────────┘   └──────────────────┘                  │
└───────────────────────────────┬──────────────────────────────┘
                                │
┌───────────────────────────────▼──────────────────────────────┐
│                  Agent Wallet (OWS-compliant)                 │
│                                                              │
│         Transaction execution  ·  Asset custody              │
└──────────────────────────────────────────────────────────────┘
```

---

## Components

### Frontend (React)

The frontend provides the human-facing interface for:

- **Agent Dashboard** — displays active agents, their wallets, and pending transactions.
- **Policy Manager** — create, edit, and activate governance policies (spend limits, time windows, recipient allow-lists, asset type restrictions).
- **Audit Log Viewer** — browse the immutable log of every governance decision with its proof record.
- **Escalation Queue** — human reviewers see and act on escalated transactions here.

**Tech stack:** React 18, TypeScript, Vite, Tailwind CSS

---

### Backend (FastAPI)

The backend exposes the REST API consumed by the frontend and by agent wallets directly.

Key responsibilities:
- Route incoming transaction requests to the governance layer.
- Persist policy definitions and audit records.
- Manage WebSocket connections for real-time escalation notifications.
- Handle authentication and session management.

**Tech stack:** Python 3.11+, FastAPI, Pydantic, SQLite (dev) / PostgreSQL (prod)

---

### CompliAGL Governance Layer

The core of the project. Four sub-engines work in sequence for every governance decision:

#### 1. Policy Engine

Stores and retrieves active policies for each agent. A policy is a set of rules such as:

```json
{
  "agent_id": "agent-007",
  "max_spend_per_tx": 100.00,
  "allowed_assets": ["USDC", "ETH"],
  "allowed_recipients": ["0xabc...", "0xdef..."],
  "allowed_hours_utc": [9, 17]
}
```

#### 2. Decision Engine

Takes a proposed transaction and evaluates it against every active policy rule. Returns one of three verdicts:

- `APPROVED` — all rules pass.
- `DENIED` — one or more rules fail with no override path.
- `ESCALATED` — rules are ambiguous or an override threshold was reached.

#### 3. Proof Engine

For every decision, the proof engine produces a **proof record**:

```json
{
  "decision_id": "d-20240315-001",
  "verdict": "APPROVED",
  "agent_id": "agent-007",
  "transaction_hash": "0x1234...",
  "policy_snapshot": { ... },
  "timestamp": "2024-03-15T10:23:00Z",
  "signature": "0xabcd..."
}
```

This record is stored in the audit log and can be exported or anchored on-chain.

#### 4. Escalation Engine

When the decision engine returns `ESCALATED`, the escalation engine:

1. Pauses the agent wallet transaction.
2. Notifies the assigned human reviewer via the dashboard.
3. Waits for an approve or deny response.
4. Records the human decision in the proof record and resumes or blocks the transaction accordingly.

---

## Data Flow

```
Agent proposes transaction
         │
         ▼
  Backend API receives request
         │
         ▼
  Policy Engine loads active policies
         │
         ▼
  Decision Engine evaluates rules
         │
    ┌────┴────┐
    │         │
 APPROVED   DENIED    ──► Proof generated ──► Audit log
    │
    ▼
 ESCALATED ──► Human reviewer notified
               │
         ┌─────┴─────┐
      APPROVE       DENY
         │             │
    Proof generated  Proof generated
         │             │
      Wallet        Wallet
      executes      blocked
```

---

## Future Integration Points

### OWS (Open Wallet Standard)

CompliAGL is designed to plug directly into OWS-compliant agent wallets as a **pre-execution middleware hook**. The governance layer intercepts every wallet action before it reaches the execution layer, ensuring no transaction bypasses policy review.

### x402 Payment Protocol

Support for x402 will allow CompliAGL to govern real-time micro-payments made by agents — applying the same policy, proof, and escalation logic to high-frequency, low-value transactions.

### Blockchain Proof Anchoring

Proof records can be anchored to a public blockchain (e.g., Ethereum, Base) for immutable, tamper-evident audit trails that exist independently of the CompliAGL database.

### DAO-Based Policy Governance

Policies themselves can be governed by a DAO, where token holders vote on rule changes, spending limit increases, or escalation thresholds — creating a fully decentralized governance stack for agent wallets.
