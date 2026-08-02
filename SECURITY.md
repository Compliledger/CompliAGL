# Security Policy

## Project status

CompliAGL is in **active development / proof-of-concept** stage. It is **not**
hardened for production use. In particular, be aware of the following current
limitations before deploying it anywhere non-local:

- **Authentication is a placeholder.** `app/core/security.py` performs a simple
  API-key equality check against `SECRET_KEY`. There is no user authentication,
  session management, or OAuth/JWT integration.
- **Tenant isolation is transport-level.** The canonical API requires an
  `X-Organization-Id` header (or `organization_id` query parameter) but does not
  verify caller identity behind that header.
- **CORS is fully permissive** (`allow_origins=["*"]`) for local development.
- **Signing keys default to a development key** derived from `SECRET_KEY` when
  no explicit keys are configured. Supply real, environment-backed keys
  (`AIPROOF_SIGNING_KEYS`, `AUTHORIZATION_SIGNING_KEYS`, `EVENT_SIGNING_KEYS`)
  via secret management before relying on signatures.
- **AIProof signing defaults to HMAC-SHA256** (symmetric). Asymmetric signing is
  supported by the interface but not the default.
- **On-chain anchoring is optional and adapter-based.** When the external
  adapter is absent, proofs are **not** anchored (`anchored: false`).

## Handling secrets

- Never commit private signing keys or facilitator credentials. Provide them via
  environment variables / a secrets manager (see `backend/.env.example`).
- The committed `.env.example` files contain only non-secret defaults.

## Reporting a vulnerability

If you believe you have found a security issue, please open a **private**
report to the maintainers rather than a public issue, and include:

- a description of the issue and its impact,
- steps to reproduce,
- affected files or endpoints.

Because this is a pre-production project, please do not assume any deployment is
externally reachable or production-grade.
