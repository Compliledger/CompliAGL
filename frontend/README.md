# CompliAGL — Frontend

## Overview

The CompliAGL frontend is a **React + Vite** single-page application that provides a governance dashboard for agent wallet operators. It is responsible for:

- **Transaction Feed** — Real-time view of incoming transaction requests and their current status.
- **Decision Inspector** — Drill into any decision to see the policy that was evaluated, the verdict returned, and the proof bundle generated.
- **Policy Manager** — Create, edit, and version spend-control policies and escalation rules.
- **Audit Trail** — Browse the full, immutable audit log with filters and search.
- **Agent Overview** — Monitor registered agents, their wallets, and recent activity.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | React 18 |
| Build Tool | Vite |
| Language | TypeScript |
| Styling | Tailwind CSS |
| HTTP Client | Axios / Fetch |

## Getting Started

```bash
cd frontend
npm install
npm run dev
```

The app will be available at **http://localhost:5173**.

> **Note:** This service is under active development as part of the MVP / hackathon build. Components and routes may change.
