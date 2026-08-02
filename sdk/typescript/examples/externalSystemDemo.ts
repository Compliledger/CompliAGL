import { CompliAGLClient, ExecutionResultStatus, attachResultSignature } from '../src';
import { startMockServer } from '../test/mockServer';

const usingExternal = Boolean(process.env.COMPLIAGL_BASE_URL);
const mock = usingExternal ? undefined : await startMockServer();
const client = new CompliAGLClient({
  baseUrl: process.env.COMPLIAGL_BASE_URL ?? mock!.baseUrl,
  organizationId: process.env.COMPLIAGL_ORG_ID ?? 'test-org',
  apiKey: process.env.COMPLIAGL_API_KEY ?? 'test-key',
});

try {
  console.log('CompliAGL lifecycle demo. External app: OUTSIDE CompliAGL generic fulfillment system.');
  const actor = await client.actorIdentities.create({ externalActorId: 'fulfillment-agent-001', actorType: 'AGENT', displayName: 'Outside Fulfillment Agent' });
  const target = await client.targets.create({ externalTargetId: 'supplier-001', targetType: 'MERCHANT', displayName: 'Outside Supplier' });
  const intent = await client.intents.create({ actorIdentityId: actor.id, action: 'PURCHASE', targetId: target.id, amount: 2500, currency: 'USD', payload: { item: 'standard-service' } });
  const context = await client.operationalContexts.create({ intentId: intent.id, targetId: target.id, environment: 'production', facts: { channel: 'demo' } });
  console.log('1 create actor/intent/target/context', actor.id, intent.id, target.id, context.id);
  const evaluation = await client.evaluations.create({ intentId: intent.id, operationalContextId: context.id });
  const resolved = await client.evaluations.resolve(evaluation.id);
  console.log('2 evaluation resolved', resolved.result);
  const source = await client.evidence.createSource({ sourceType: 'external-context', payload: { customerTier: 'standard' } });
  const collection = await client.evidence.createCollection({ evaluationId: evaluation.id, evidenceSourceIds: [source.id] });
  console.log('3 evidence collected', collection.id);
  const decision = await client.decisions.decide({ intentId: intent.id, evaluationId: evaluation.id, evidenceCollectionId: collection.id });
  console.log('4 decision read from CompliAGL', decision.outcome);
  const authorization = await client.authorizations.issue({ decisionId: decision.id });
  console.log('5 authorization issued', authorization.id, 'cap', authorization.approvedAmount);
  const authorizationCheck = await client.authorizations.verify(authorization.id);
  console.log('6 authorization verified', authorizationCheck.valid);
  console.log('7 OUTSIDE CompliAGL system executes generic fulfillment');
  const now = new Date().toISOString();
  const signed = attachResultSignature({ executionResultId: 'outside-result-100', authorizationId: authorization.id, externalSystemId: 'outside-fulfillment', status: ExecutionResultStatus.SUCCEEDED, executedAction: 'CAPTURE', target: { targetId: target.id, type: 'MERCHANT' }, amountMinor: 2500, amountCurrency: 'USD', externalReference: 'outside-order-100', paymentOrSettlementReference: 'settlement-100', executedAt: now, submittedAt: now, signerKeyId: 'demo-key-1', provenance: { system: 'outside-fulfillment', outsideCompliagl: true }, resultPayload: { fulfilled: true, capturedMinor: 2500 } }, 'result-secret');
  const result = await client.executionResults.submit(signed, { idempotencyKey: 'demo-result' });
  const binding = await client.verification.verifyExecutionResultBinding({ resultId: result.id });
  console.log('8 signed result submitted and binding valid', binding.valid);
  const proof = await client.aiproofs.generate({ resultId: result.id });
  const proofCheck = await client.aiproofs.verify(proof.id);
  console.log('9 AIProof generated and verified', proofCheck.verified, proof.id);
  console.log('Demo complete. CompliAGL authorized and proved; execution happened outside CompliAGL.');
} finally {
  await mock?.close();
}
