import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import { AuthorizationStatus, CompliAGLClient, ConflictError, DecisionOutcome, ExecutionResultStatus, ValidationError, attachResultSignature, hashResultPayload, resultSigningString, signWebhookPayload, verifyResultSignature, verifyWebhookSignature } from '../src';
import { DecisionClient } from '../src/clients/decisions';
import { AuthorizationClient } from '../src/clients/authorizations';
import { startMockServer, type MockServerHandle } from './mockServer';

let server: MockServerHandle;
let client: CompliAGLClient;
beforeEach(async () => { server = await startMockServer(); client = new CompliAGLClient({ baseUrl: server.baseUrl, apiKey: 'test-key', organizationId: 'test-org', retry: { baseDelayMs: 1, jitter: false } }); });
afterEach(async () => { await server.close(); });

async function lifecycle(amountMinor = 4200) {
  const actor = await client.actorIdentities.create({ externalActorId: 'actor-1', actorType: 'AGENT', displayName: 'Procurement bot' });
  const target = await client.targets.create({ externalTargetId: 'target-1', targetType: 'MERCHANT', displayName: 'Outside supplier', attributes: { category: 'generic' } });
  const intent = await client.intents.create({ actorIdentityId: actor.id, action: 'PURCHASE', targetId: target.id, amount: amountMinor, currency: 'USD', payload: { sku: 'MRO-1' } });
  const transitionedIntent = await client.intents.transition(intent.id, { status: 'READY_FOR_EVALUATION' });
  const context = await client.operationalContexts.create({ intentId: intent.id, targetId: target.id, environment: 'production', facts: { requestedBy: 'ops' } });
  const evaluation = await client.evaluations.create({ intentId: intent.id, operationalContextId: context.id });
  const resolvedEvaluation = await client.evaluations.resolve(evaluation.id);
  const source = await client.evidence.createSource({ sourceType: 'purchase-order', payload: { approvedBy: 'manager' } });
  const collection = await client.evidence.createCollection({ evaluationId: evaluation.id, evidenceSourceIds: [source.id], artifacts: [{ hash: 'artifact-1' }] });
  const decision = await client.decisions.decide({ intentId: intent.id, evaluationId: evaluation.id, evidenceCollectionId: collection.id });
  const explanation = await client.decisions.explain(decision.id);
  const authorization = await client.authorizations.issue({ decisionId: decision.id });
  const verifiedAuthorization = await client.authorizations.verify(authorization.id);
  const now = new Date().toISOString();
  const signed = attachResultSignature({
    executionResultId: 'result-1',
    authorizationId: authorization.id,
    externalSystemId: 'outside-fulfillment',
    status: ExecutionResultStatus.SUCCEEDED,
    executedAction: 'CAPTURE',
    target: { targetId: target.id, type: 'MERCHANT' },
    amountMinor,
    amountCurrency: 'USD',
    externalReference: 'outside-order-1',
    paymentOrSettlementReference: 'settlement-1',
    executedAt: now,
    submittedAt: now,
    signerKeyId: 'test-key-1',
    provenance: { system: 'outside-fulfillment', operator: 'integration-test' },
    resultPayload: { captured: amountMinor, reference: 'CAP-1' },
  }, 'result-secret');
  const result = await client.executionResults.submit(signed, { idempotencyKey: 'result-key' });
  const binding = await client.verification.verifyExecutionResultBinding({ resultId: result.id });
  const proof = await client.aiproofs.generate({ resultId: result.id });
  const verifiedProof = await client.aiproofs.verify(proof.id);
  return { actor, target, intent: transitionedIntent, context, evaluation: resolvedEvaluation, source, collection, decision, explanation, authorization, verifiedAuthorization, result, binding, proof, verifiedProof, signed };
}

describe('CompliAGL TypeScript SDK spec client set', () => {
  it('exposes exactly the 11 logical aggregate client properties', () => {
    expect(Object.keys(client).filter(k => k !== 'http').sort()).toEqual(['actorIdentities','aiproofs','authorizations','decisions','evaluations','evidence','executionResults','intents','operationalContexts','targets','verification'].sort());
    expect(client).not.toHaveProperty('governancePackages');
    expect(client).not.toHaveProperty('policies');
    expect(client).not.toHaveProperty('transactions');
    expect(client).not.toHaveProperty('policyApplicability');
    expect(client).not.toHaveProperty('externalExecutions');
    expect(client).not.toHaveProperty('agentIdentities');
  });

  it('performs CRUD and endpoint actions across the required clients and maps errors', async () => {
    const actor = await client.actorIdentities.create({ externalActorId: 'a', actorType: 'AGENT', displayName: 'A' });
    expect((await client.actorIdentities.list()).length).toBe(1);
    expect((await client.actorIdentities.update(actor.id, { displayName: 'B' })).displayName).toBe('B');
    await client.actorIdentities.delete(actor.id);
    await expect(client.actorIdentities.get(actor.id)).rejects.toMatchObject({ name: 'NotFoundError' });
    await expect(new CompliAGLClient({ baseUrl: server.baseUrl, apiKey: 'bad', organizationId: 'test-org' }).actorIdentities.list()).rejects.toMatchObject({ name: 'AuthenticationError' });
  });

  it('retries retryable responses honoring Retry-After', async () => {
    await expect(client.http.get<{ ok: boolean; attempts: number }>('/flaky')).resolves.toEqual({ ok: true, attempts: 3 });
  });

  it('replays idempotent creates', async () => {
    const input = { externalActorId: 'idem-actor', actorType: 'AGENT', displayName: 'Idem' };
    const a = await client.actorIdentities.create(input, { idempotencyKey: 'same-create' });
    const b = await client.actorIdentities.create(input, { idempotencyKey: 'same-create' });
    expect(b.id).toBe(a.id);
    expect((await client.actorIdentities.list()).length).toBe(1);
  });

  it('verifies webhook signatures and rejects tampered or expired payloads', () => {
    const payload = JSON.stringify({ event: 'external-execution-result.created' });
    const ts = Math.floor(Date.now() / 1000);
    const signature = signWebhookPayload('webhook-secret', payload, ts);
    expect(verifyWebhookSignature({ secret: 'webhook-secret', payload, timestamp: ts, signature })).toBe(true);
    expect(verifyWebhookSignature({ secret: 'webhook-secret', payload: payload + 'x', timestamp: ts, signature })).toBe(false);
    expect(verifyWebhookSignature({ secret: 'webhook-secret', payload, timestamp: ts - 1_000, signature })).toBe(false);
  });

  it('hashes, signs, and verifies execution results', () => {
    const executedAt = new Date().toISOString();
    const submittedAt = executedAt;
    const resultPayload = { z: 1, a: { b: 2 } };
    const resultPayloadHash = hashResultPayload(resultPayload);
    const signed = attachResultSignature({ executionResultId: 'res', authorizationId: 'auth', externalSystemId: 'sys', status: ExecutionResultStatus.SUCCEEDED, executedAction: 'CAPTURE', target: { id: 'target' }, amountMinor: 123, amountCurrency: 'USD', externalReference: 'ext', paymentOrSettlementReference: 'pay', executedAt, submittedAt, signerKeyId: 'key-1', provenance: { source: 'test' }, resultPayload }, 'secret');
    expect(signed.resultPayloadHash).toBe(resultPayloadHash);
    expect(resultSigningString(signed).split('\n')).toHaveLength(13);
    expect(verifyResultSignature({ executionResultId: 'res', authorizationId: 'auth', externalSystemId: 'sys', status: ExecutionResultStatus.SUCCEEDED, executedAction: 'CAPTURE', target: { id: 'target' }, amountMinor: 123, amountCurrency: 'USD', externalReference: 'ext', paymentOrSettlementReference: 'pay', resultPayloadHash, executedAt, submittedAt }, signed.signature, 'secret')).toBe(true);
  });

  it('runs the full 9-step lifecycle with authorization verification, binding validation, and AIProof verification', async () => {
    const { decision, authorization, verifiedAuthorization, binding, proof, verifiedProof } = await lifecycle(7300);
    expect(decision.outcome).toBe(DecisionOutcome.APPROVED);
    expect(authorization.status).toBe(AuthorizationStatus.ISSUED);
    expect(verifiedAuthorization.valid).toBe(true);
    expect(binding.valid).toBe(true);
    expect(proof.verificationStatus).toBe('VERIFIED');
    expect(verifiedProof.verified).toBe(true);
    await expect(client.verification.verifyAuthorization({ authorizationId: authorization.id })).resolves.toEqual({ valid: true });
    await expect(client.verification.verifyProof({ proofId: proof.id })).resolves.toEqual({ valid: true });
  });

  it('rejects altered results: over-cap as ConflictError and result_payload_hash mismatch as ValidationError', async () => {
    const { authorization, signed } = await lifecycle(1000);
    const now = new Date().toISOString();
    const overCap = attachResultSignature({ executionResultId: 'over-cap', authorizationId: authorization.id, externalSystemId: 'outside-fulfillment', status: ExecutionResultStatus.SUCCEEDED, executedAction: 'CAPTURE', target: 'merchant-1', amountMinor: 1001, amountCurrency: 'USD', executedAt: now, submittedAt: now, signerKeyId: 'test-key-1', provenance: { system: 'outside-fulfillment' }, resultPayload: { captured: 1001 } }, 'result-secret');
    await expect(client.executionResults.submit(overCap)).rejects.toBeInstanceOf(ConflictError);
    await expect(client.executionResults.submit({ ...signed, executionResultId: 'tampered', resultPayload: { captured: 999 } })).rejects.toBeInstanceOf(ValidationError);
  });

  it('keeps policy and decision logic out of the SDK core', () => {
    const combined = [DecisionClient.prototype.decide, AuthorizationClient.prototype.issue].map(fn => fn.toString()).join('\n');
    expect(combined).not.toContain('APPROVED');
    expect(combined).not.toContain('DENIED');
    expect(combined).not.toContain('authorizationCap');
    expect(combined).not.toContain('approvedAmount');
  });
});
