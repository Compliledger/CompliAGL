# CompliAGL Python SDK

`compliagl-sdk` is the Python Integration SDK for external systems that drive the CompliAGL governed-execution lifecycle over HTTP. The import package is `compliagl` and Python 3.10+ is supported. Runtime dependencies are standard library only.

## Install

```bash
pip install compliagl-sdk
```

For local development:

```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## Quickstart

```python
from compliagl import CompliAGL, CompliAGLConfig

sdk = CompliAGL(CompliAGLConfig(
    base_url="http://localhost:8000",
    organization_id="org_123",
    api_key="optional-api-key",
    auto_idempotency=True,
))

actor = sdk.actor_identities.create({"actor_type": "SERVICE", "credential_type": "NONE"})
```

Every request includes `X-Organization-Id`. If `api_key` is set, the SDK sends an authorization bearer token.

## The 11 clients

The aggregate `CompliAGL` client exposes:

- `actor_identities` — create/list/get/update actor identities
- `intents` — create/list/get/update intents and transition status
- `targets` — create/list/get/update targets
- `operational_contexts` — create/list/get/update contexts
- `evaluations` — create/list/get evaluations and resolve outcomes returned by CompliAGL/mock
- `evidence` — create evidence collections, get jobs/packages, list sources
- `decisions` — create/list/get decisions, call `decide`, and explain
- `authorizations` — create/issue/verify/consume/revoke/transition execution authorizations
- `execution_results` — submit/list/get signed external execution results
- `aiproofs` — generate/get/list/verify AIProofs
- `verification` — helper calls for authorization/proof verification plus local result signature checks

CamelCase aliases are provided for common aggregate properties such as `actorIdentities`, `operationalContexts`, and `executionResults`.

## Auth, retries, and idempotency

Transport uses `urllib.request`. GET requests and POST requests with an idempotency key are retried on network errors and HTTP 408/429/500/502/503/504 using exponential backoff with jitter and `Retry-After` support. POST calls accept `idempotency_key=...`; set `auto_idempotency=True` to generate UUIDv4 keys automatically. Timeouts and retry settings are configurable.

Typed errors include `NotFoundError`, `ValidationError`, `ConflictError`, `RateLimitError`, `AuthError`, and `ServerError`.

## Result signing and webhook verification

Use `sign_execution_result` or `ResultSigner` to hash the canonical JSON result payload and HMAC-sign the canonical binding string. Use `verify_execution_result_signature` for local structural/cryptographic checks.

`verify_webhook_signature(payload, headers, secret)` verifies `X-CompliAGL-Signature` and `X-CompliAGL-Timestamp` with constant-time comparison and timestamp tolerance.

## Adapter interfaces

`compliagl.adapters` defines Protocols for external applications: `AgentIdentityProvider`, `EvidenceProvider`, `ExternalExecutionSystem`, `MerchantSystem`, `PaymentSystem`, `HederaAgentAccount`, and `ProofVerifier`. Core SDK provides interfaces only; concrete execution belongs in your application.

## Lifecycle

1. External app selects an offer/action.
2. SDK creates actor, intent, target, operational context.
3. SDK requests evaluation and reads a CompliAGL decision.
4. SDK requests an execution authorization.
5. SDK verifies authorization.
6. External app performs the real action.
7. SDK signs and submits the external execution result.
8. CompliAGL validates result binding.
9. SDK requests and verifies an AIProof.

## What CompliAGL does NOT do / external execution happens outside CompliAGL

CompliAGL does not perform merchant sales, bookings, payments, fulfillment, inventory changes, or wallet custody. Those actions happen in the external system. This SDK contains no policy or decision logic; it only calls CompliAGL APIs and performs cryptographic/structural verification.

## Run tests and example

```bash
pytest -q
python examples/external_system_demo.py
```

The example starts the in-repo mock server by default. Override with `COMPLIAGL_BASE_URL`, `COMPLIAGL_ORG_ID`, and `COMPLIAGL_API_KEY` to point at a real backend.
