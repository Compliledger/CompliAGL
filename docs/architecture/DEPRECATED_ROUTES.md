# CompliAGL — Deprecated Routes & Modules

Phase 1 consolidation keeps backward compatibility where practical. The
following routes and modules are **deprecated**: they still work during the
deprecation window but must not be used by new code, and they are not part of
the canonical persistent runtime.

## Deprecated HTTP routes

| Route | Reason | Canonical replacement |
| --- | --- | --- |
| `POST /api/mvp2/evaluate` | In-memory decision engine | `POST /api/compli402/verify/intent` (persistent decision engine) |
| `GET /api/mvp2/actors` | In-memory actor registry | persistent actors via `actor_registry` |
| `GET /api/mvp2/policies` | In-memory policy store | persistent policies via `policy_repository` |
| `POST /api/mvp2/execute` | Execution decoupled from persistent intent | Compli402 execute flow / execution adapters |
| `POST /api/mvp2/proofs/generate` | In-memory proof store | persistent AIProof (`aiproof_service`) |
| `GET /api/mvp2/proofs` | In-memory proof store | `GET /api/compli402/proofs/latest` + `/{proof_hash}` |
| `GET /api/mvp2/proofs/{proof_id}` | In-memory proof store | `GET /api/compli402/proofs/{proof_hash}` |
| `POST /transactions/{id}/evaluate` | Transaction-centric model, not canonical | Compli402 intent flow |

All MVP2 routers are registered with `deprecated=True` so they render as
deprecated in the OpenAPI docs.

## Deprecated modules

| Module | Reason | Canonical replacement |
| --- | --- | --- |
| `app/mvp2/identity/actors.py` (`_ACTOR_REGISTRY`, `seed_demo_actors`) | in-memory actor registry | `app/services/actor_registry.py` |
| `app/mvp2/core/policy_engine.py` (`_POLICY_STORE`, `seed_demo_policies`) | in-memory policy store | `app/services/policy_repository.py` (+ `evaluate_policies` reused as the rule core) |
| `app/mvp2/core/decision_engine.py` | orchestrator over in-memory policies | `app/services/decision_engine.py` |
| `app/mvp2/api/routes/proof.py` (`_PROOF_STORE`) | in-memory proof store | `app/services/aiproof_service.py` |
| `app/models/proof_bundle.py` + `app/services/proof_service.py` | superseded proof model | `app/models/aiproof.py` + `app/services/aiproof_service.py` |
| `app/utils/rule_engine.py` + `app/services/evaluation_service.py` | transaction-centric engine | `app/services/decision_engine.py` |

## Notes

- The deprecated modules are **not** invoked by the production startup path.
  Startup now seeds the **database** (`app/db/seed.py`).
- The `evaluate_policies` function in `policy_engine.py` is retained as the
  shared deterministic **rule core** used by the canonical decision engine; the
  in-memory `_POLICY_STORE` around it is what is deprecated.
