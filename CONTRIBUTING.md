# Contributing to CompliAGL

Thanks for your interest in CompliAGL. This project is in active development, so
interfaces and schemas may change.

## Repository layout

| Path | What it is |
|------|------------|
| `backend/` | FastAPI control plane (Python, SQLAlchemy, Pydantic v2) |
| `CompliAgl-Frontend/` | Next.js + React + TypeScript operator/landing surface |
| `sdk/typescript/`, `sdk/python/` | Thin, typed client SDKs (unpublished, v0.1.0) |
| `docs/` | Architecture, integration contracts, demo flows, AIProof schema |
| `assets/` | Repository-native SVG diagrams |

## Development setup

See [QUICKSTART.md](./QUICKSTART.md) for verified setup, run, and test commands.

## Backend guidelines

- Prefer the **canonical** runtime (`app/api/v1`, `app/services/canonical`,
  `app/models`) over the deprecated in-memory `app/mvp2` surface.
- Add or update **Alembic migrations** in `backend/migrations/versions/` when
  you change persistent models.
- Run the test suite before submitting changes:

  ```bash
  cd backend && pip install pytest httpx && python -m pytest -q
  ```

- Keep new capabilities honestly labeled. If something is a mock, adapter stub,
  or in-memory default, say so in code comments and docs.

## Frontend guidelines

From `CompliAgl-Frontend/`:

```bash
npm run lint
npm run typecheck
npm run format:check
```

## Commit / PR expectations

- Keep changes focused and describe what was verified.
- Do not introduce badges, claims, or documentation that overstate
  implementation status (see `README.md` and `ROADMAP.md` for the accuracy bar).
- Do not commit secrets. Use environment-backed configuration.

## Reporting security issues

See [SECURITY.md](./SECURITY.md).
