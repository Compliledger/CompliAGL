# CompliAGL Integration SDK

The **CompliAGL Integration SDK** lets external systems drive the CompliAGL
governed-execution lifecycle over HTTP. It is a thin, typed API client for the
CompliAGL control plane.

> **The SDK contains no policy or decision logic.** Every governance decision is
> made server-side by CompliAGL. The SDK only submits governance inputs, retrieves
> decisions, verifies authorizations, submits externally-produced execution
> results, and retrieves/verifies the resulting **AIProof**.

## What CompliAGL does — and does NOT — do

CompliAGL is the control plane for **governed autonomous execution**. It authorizes
an action *before* it happens and produces a verifiable **AIProof** *after*.

CompliAGL **does not** perform any of the following — these always happen in the
**external system**, outside CompliAGL:

- merchant sales
- flight bookings
- payment settlement
- inventory fulfillment
- wallet custody

The external application selects offers, performs the real action, and reports the
outcome. CompliAGL governs and proves; it never executes the business action.

## The external execution boundary (lifecycle)

```
[EXTERNAL]  1. Create/submit actor, intent, target, operational context
   SDK  ->  2. Request evaluation
CompliAGL -> 3. Return Decision
   SDK  ->  4. If APPROVED, receive a signed ExecutionAuthorization
   SDK  ->  5. Verify the authorization
[EXTERNAL]  6. Perform the action (ExternalExecutionSystem adapter)
   SDK  ->  7. Submit a signed ExternalExecutionResult
CompliAGL -> 8. Validate result binding (altered results are rejected)
CompliAGL -> 9. Generate AIProof  ->  SDK retrieves & verifies it
```

Steps 1, 5, and 7 are performed by the **SDK calling CompliAGL APIs**. Steps 3, 8,
and 9 happen **inside CompliAGL**. Step 6 (the real action) always happens in the
**external system** — never inside CompliAGL.

## Packages

| Language   | Package            | Location          |
|------------|--------------------|-------------------|
| TypeScript | `@compliagl/sdk`   | [`typescript/`](./typescript) |
| Python     | `compliagl-sdk`    | [`python/`](./python) |

Both packages expose the same logical surface.

### Logical clients

1. `ActorIdentityClient`
2. `IntentClient`
3. `TargetClient`
4. `OperationalContextClient`
5. `EvaluationClient`
6. `EvidenceClient`
7. `DecisionClient`
8. `AuthorizationClient`
9. `ExecutionResultClient`
10. `AIProofClient`
11. `VerificationClient`

### Adapter interfaces

The external application implements these adapters (the SDK ships the interfaces,
not the implementations — concrete, simulated implementations live in the examples,
clearly outside CompliAGL):

- `AgentIdentityProvider`
- `EvidenceProvider`
- `ExternalExecutionSystem`
- `MerchantSystem`
- `PaymentSystem`
- `HederaAgentAccount`
- `ProofVerifier`

## Cross-cutting features

- **Authentication** — bearer API key + `X-Organization-Id` tenant header.
- **Retries** — exponential backoff with jitter on transient failures (`Retry-After` aware).
- **Idempotency** — `Idempotency-Key` header on mutating requests.
- **Result signing** — HMAC-SHA256 signing of `ExternalExecutionResult` bound to the
  authorization; CompliAGL rejects altered results.
- **Webhook signature verification** — HMAC-SHA256 with timestamp replay protection.

See each package's own README for install, quickstart, examples, and test instructions.
