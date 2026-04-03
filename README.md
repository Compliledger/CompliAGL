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

---

## License

This project is licensed under the terms specified in the repository. See [LICENSE](LICENSE) for details.
