# CompliAGL — Quickstart

This guide contains **verified** commands for running CompliAGL locally. Every
command was checked against the repository as it exists today.

> **Status:** Active development / proof of concept. The backend runs on SQLite
> with permissive CORS and a placeholder API-key check — it is **not** a
> production deployment.

## Prerequisites

- **Python 3.10+** (3.11+ recommended) for the backend
- **Node.js 20+** and **npm** for the frontend
- **git**

## 1. Clone

```bash
git clone https://github.com/Compliledger/CompliAGL.git
cd CompliAGL
```

## 2. Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate            # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Optional environment file (defaults work out of the box with SQLite):

```bash
cp .env.example .env                 # from the backend/ directory
```

Start the API (tables are created and demo actors/policies are seeded on boot):

```bash
uvicorn app.main:app --reload --port 8000
```

- Interactive OpenAPI docs: <http://localhost:8000/docs>
- Health check: <http://localhost:8000/health>
- Canonical runtime API is served under `/api/v1`

The default database is `sqlite:///./compliagl.db`. `app.main` calls
`init_db()` (SQLAlchemy `create_all`) on startup, so migrations are **not**
required for local runs. Alembic migrations live in `backend/migrations/` for
reference and non-SQLite targets.

## 3. Frontend

The frontend is a separate Next.js app in `CompliAgl-Frontend/`.

```bash
cd CompliAgl-Frontend
npm install
npm run dev
```

Next.js serves on <http://localhost:3000> by default.

> **Note:** The root `Makefile` references a `frontend/` directory and port
> `5173`; the actual frontend directory is `CompliAgl-Frontend/` and Next.js
> uses port `3000`. Prefer the commands above.

## 4. Tests

Backend tests are written with **pytest** and use FastAPI's `TestClient`
(`httpx`). Neither is pinned in `backend/requirements.txt`, so install them
before running the suite:

```bash
cd backend
pip install pytest httpx
python -m pytest -q
```

The frontend has no automated test suite; it exposes `lint`, `typecheck`, and
`format` scripts (see `CompliAgl-Frontend/package.json`).

## 5. Optional: Algorand anchoring adapter

On-chain anchoring is delegated to the **optional, external**
`compliledger-algorand-adapter`, which is **not** included in this repository.
When it is absent, anchoring degrades gracefully (`anchored: false`) and the
rest of the system continues to run. See
`backend/app/mvp2/anchor/README.md` and `backend/requirements-adapter.txt`.

## 6. Demo flow

A payment-gated demo (`Compli402`) is exposed under `/api/compli402` and uses a
built-in **mock** x402 facilitator by default (`X402_MOCK_MODE=true`), so it
runs with no external services or secrets. See `docs/demo-flow.md`.
