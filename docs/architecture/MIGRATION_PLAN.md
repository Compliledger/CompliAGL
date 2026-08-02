# CompliAGL Consolidation — Migration Plan

This plan describes the persistence and code migrations performed in Phase 1
(architecture consolidation), and how to run them.

## 1. Persistence changes

Before this phase the schema was created implicitly at startup via
`Base.metadata.create_all()` and there was **no migration tooling**. Phase 1
introduces **Alembic** and adds the canonical proof table.

### New table: `ai_proofs`

Canonical persistent AIProof (unifies `ProofBundle` + `AIProofBundle`).

| Column | Type | Notes |
| --- | --- | --- |
| `proof_id` | String, PK | AIProof identifier |
| `proof_type` | String | e.g. `compli402.execution` |
| `actor_id` | String, indexed | acting entity |
| `actor_identity` | Text (JSON) | resolved actor snapshot |
| `intent_id` | String, indexed | governed intent / transaction id |
| `intent` | Text (JSON) | action / amount / currency |
| `policy_id` | String, nullable | governing policy |
| `policy_version` | String | policy version |
| `decision` | String | `APPROVED` / `DENIED` / `ESCALATED` |
| `decision_reason` | Text (JSON) | reason codes |
| `execution_adapter` | String, nullable | adapter used |
| `execution_status` | String, nullable | external execution outcome |
| `payment_protocol` | String, nullable | optional (e.g. `x402`) |
| `payment_reference` | String, nullable | external settlement reference |
| `settlement_chain` | String, nullable | network the payment settled on |
| `anchor_chain` | String, nullable | proof anchor chain |
| `anchor_tx_id` | String, nullable | on-chain anchor tx id (post-hash) |
| `proof_hash` | String, indexed | deterministic SHA-256 binding |
| `created_at` | String | ISO 8601 UTC |
| `verification_url` | String, nullable | post-hash verification URL |

The deprecated `proof_bundles` table is retained (no data migration) for
backward compatibility with the legacy `/transactions` evaluate flow.

### Deprecated (retained) tables

`transactions`, `approvals`, `proof_bundles` remain in the schema for backward
compatibility but are **not** part of the canonical runtime path.

## 2. Alembic layout

```
backend/
  alembic.ini
  migrations/
    env.py
    script.py.mako
    versions/
      0001_baseline.py        # baseline: agents, policies, transactions,
                              # approvals, audit_logs, proof_bundles
      0002_add_ai_proofs.py   # new canonical ai_proofs table
```

`migrations/env.py` imports `app.core.database.Base` and every model module so
`target_metadata` reflects the full schema, and it reads the database URL from
`app.core.config.settings.DATABASE_URL`.

## 3. Running the migrations

From `backend/`:

```bash
# Upgrade to the latest revision (creates ai_proofs and baseline tables)
alembic upgrade head

# Inspect current revision
alembic current

# Downgrade the ai_proofs table only
alembic downgrade -1
```

For local development the application still calls `init_db()` at startup, which
uses `create_all()` and is idempotent with the Alembic-managed schema (Alembic
is the source of truth for production deployments).

## 4. Runtime data (seed)

Startup seeds the **database** (not in-memory) with a canonical demo actor and
policy so the Compli402 flow works out of the box:

- Demo actor `TravelAgent-01` — id `00000000-0000-0000-0000-000000000001`.
- Demo policy `Travel Spend Policy` bound to that actor:
  `per_tx_limit=500`, `escalation_threshold=250`, blocked asset `BTC`.

Seeding is idempotent and survives restart because it is persisted.

## 5. Rollback

- `alembic downgrade -1` drops `ai_proofs`.
- The deprecated in-memory modules remain importable, so any external code that
  still imports them keeps working during the deprecation window.
