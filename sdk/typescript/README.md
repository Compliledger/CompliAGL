# @compliagl/sdk

TypeScript SDK for external systems integrating with CompliAGL. Requires Node 18+ and uses global `fetch` plus `node:crypto`; there are no runtime dependencies.

## Install

```sh
npm install @compliagl/sdk
```

## Quickstart

```ts
import { CompliAGLClient } from '@compliagl/sdk';
const client = new CompliAGLClient({ baseUrl, organizationId, apiKey });
const decision = await client.decisions.decide({ intentId, evaluationId, evidenceCollectionId });
```

## 11 logical clients

The aggregate client exposes exactly:

1. `actorIdentities` (`ActorIdentityClient`) for `/actor-identities`
2. `intents` (`IntentClient`) for `/intents` and `/intents/{id}/transition`
3. `targets` (`TargetClient`) for `/targets`
4. `operationalContexts` (`OperationalContextClient`) for `/operational-contexts`
5. `evaluations` (`EvaluationClient`) for `/governance-evaluations` and `/governance-evaluations/{id}/resolve`
6. `evidence` (`EvidenceClient`) for `/evidence-collections` and `/evidence-sources`
7. `decisions` (`DecisionClient`) for `/decisions`, `/decisions/decide`, and `/decisions/{id}/explain`
8. `authorizations` (`AuthorizationClient`) for `/execution-authorizations` plus issue, verify, consume, revoke, and transition actions
9. `executionResults` (`ExecutionResultClient`) for `/external-execution-results`
10. `aiproofs` (`AIProofClient`) for `/aiproofs/generate`, `/aiproofs`, `/aiproofs/{id}`, and `/aiproofs/{id}/verify`
11. `verification` (`VerificationClient`) for authorization, proof, and execution-result-binding verification

## Adapters

The SDK exports interfaces for `AgentIdentityProvider`, `EvidenceProvider`, `ExternalExecutionSystem`, `MerchantSystem`, `PaymentSystem`, `HederaAgentAccount`, and `ProofVerifier` so external apps can plug their own systems into CompliAGL flows.

## Auth, retries, idempotency

Requests send a bearer-token `Authorization` header and `X-Organization-Id`. Pass `{ idempotencyKey }` to create/update calls to send `Idempotency-Key`. The transport retries 408, 429, 5xx, and network failures with exponential backoff, jitter, and `Retry-After` support.

## Webhooks and result signing

Use `verifyWebhookSignature` for HMAC-SHA256 webhook verification with timestamp tolerance and constant-time comparison. Use `hashResultPayload`, `signResult`, `verifyResultSignature`, or `attachResultSignature` for external execution result binding.

## Lifecycle

A typical 9-step lifecycle is: create actor/intent/target/context, evaluate governance, resolve/decide, read an APPROVED decision, issue authorization, verify authorization, execute in an external system, sign and submit `ExternalExecutionResult`, validate result binding, then generate and verify an AIProof.

## What CompliAGL does NOT do / external execution happens outside CompliAGL

CompliAGL does not perform merchant, payment, fulfillment, or other operational execution. It returns evaluations, decisions, authorizations, and proofs. Your external application performs the real-world execution and reports signed results back. The SDK contains no policy or decision logic; it only calls HTTP endpoints and reads server responses.

## Development

```sh
npm install
npm run build
npm test
npm run example
```

The example runs against the in-process mock server by default. Set `COMPLIAGL_BASE_URL`, `COMPLIAGL_ORG_ID`, and `COMPLIAGL_API_KEY` to target another API.
