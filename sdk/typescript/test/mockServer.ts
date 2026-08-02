import http, { type IncomingMessage, type ServerResponse } from 'node:http';
import { createHmac } from 'node:crypto';
import { AuthorizationStatus, DecisionOutcome, ExecutionResultStatus, VerificationStatus, type AIProof } from '../src/models';
import { canonicalJson, hashResultPayload, verifyResultSignature } from '../src/signing';

export interface MockServerHandle { baseUrl: string; close(): Promise<void>; state: MockState; }
type Item = Record<string, any>;
interface MockState { stores: Record<string, Map<string, Item>>; idempotency: Map<string, { status: number; body: unknown }>; attempts: number; }

const resources = new Set(['/actor-identities','/intents','/targets','/operational-contexts','/governance-evaluations','/decisions','/execution-authorizations','/evidence-collections','/evidence-sources','/external-execution-results','/aiproofs']);
const resultSecret = 'result-secret';
const proofSecret = 'proof-secret';

export async function startMockServer(): Promise<MockServerHandle> {
  const state: MockState = { stores: {}, idempotency: new Map(), attempts: 0 };
  for (const r of resources) state.stores[r] = new Map();
  let nextId = 1;
  const server = http.createServer(async (req, res) => {
    try {
      if (!authorize(req, res)) return;
      const url = new URL(req.url ?? '/', 'http://localhost');
      if (url.pathname === '/flaky') {
        state.attempts++;
        if (state.attempts < 3) return json(res, 503, { message: 'try again' }, { 'Retry-After': '0' });
        return json(res, 200, { ok: true, attempts: state.attempts });
      }
      const body = await readJson(req);
      const rawKey = req.headers['idempotency-key'];
      const idemKey = rawKey ? `${req.method}:${url.pathname}:${String(rawKey)}:${canonicalJson(body)}` : undefined;
      if (idemKey && state.idempotency.has(idemKey)) {
        const cached = state.idempotency.get(idemKey)!;
        return json(res, cached.status, cached.body, { 'X-Idempotent-Replay': 'true' });
      }
      const response = route(req.method ?? 'GET', url.pathname, body, state, () => `mock_${nextId++}`);
      if (idemKey && ['POST','PATCH','PUT'].includes(req.method ?? '')) state.idempotency.set(idemKey, response);
      return json(res, response.status, response.body);
    } catch (error) {
      return json(res, 500, { message: error instanceof Error ? error.message : 'mock failure' });
    }
  });
  await new Promise<void>(resolve => server.listen(0, '127.0.0.1', resolve));
  const addr = server.address();
  if (!addr || typeof addr === 'string') throw new Error('mock server failed to bind');
  return { baseUrl: `http://127.0.0.1:${addr.port}`, state, close: () => new Promise<void>(resolve => server.close(() => resolve())) };
}

function route(method: string, path: string, body: any, state: MockState, id: () => string): { status: number; body: unknown } {
  const transitionIntent = path.match(/^\/intents\/([^/]+)\/transition$/);
  if (method === 'POST' && transitionIntent) return transition(state, '/intents', transitionIntent[1]!, { status: body.status });
  const resolveEvaluation = path.match(/^\/governance-evaluations\/([^/]+)\/resolve$/);
  if (method === 'POST' && resolveEvaluation) return transition(state, '/governance-evaluations', resolveEvaluation[1]!, { result: 'RESOLVED' });
  const explainDecision = path.match(/^\/decisions\/([^/]+)\/explain$/);
  if (method === 'GET' && explainDecision) return explainDecisionRoute(state, explainDecision[1]!);
  const verifyProof = path.match(/^\/aiproofs\/([^/]+)\/verify$/);
  if (method === 'POST' && verifyProof) return verifyProofRoute(state, verifyProof[1]!);

  if (method === 'POST' && path === '/decisions/decide') return createDecision(body, state, id);
  if (method === 'POST' && path === '/execution-authorizations/issue') return issueAuthorization(body, state, id);
  if (method === 'POST' && path === '/execution-authorizations/verify') return verifyAuthorizationRoute(body, state);
  if (method === 'POST' && path === '/execution-authorizations/consume') return transition(state, '/execution-authorizations', body.id, { status: AuthorizationStatus.CONSUMED });
  if (method === 'POST' && path === '/execution-authorizations/revoke') return transition(state, '/execution-authorizations', body.id, { status: AuthorizationStatus.REVOKED });
  if (method === 'POST' && path === '/execution-authorizations/transition') return transition(state, '/execution-authorizations', body.id, { status: body.status });
  if (method === 'POST' && path === '/aiproofs/generate') return generateProof(body.resultId, state, id);
  if (method === 'POST' && path === '/verification/authorization') return verifyAuthorizationRoute({ id: body.authorizationId ?? body.id }, state, true);
  if (method === 'POST' && path === '/verification/proof') return verifyProofGeneric(body, state);
  if (method === 'POST' && path === '/verification/execution-result-binding') return verifyBindingRoute(body, state);

  const [base, maybeId] = splitResource(path);
  if (!resources.has(base)) return { status: 404, body: { message: 'not found' } };
  const store = state.stores[base]!;
  if (method === 'GET' && !maybeId) return { status: 200, body: [...store.values()] };
  if (method === 'GET' && maybeId) return store.has(maybeId) ? { status: 200, body: store.get(maybeId) } : { status: 404, body: { message: 'not found' } };
  if ((method === 'PATCH' || method === 'PUT') && maybeId) {
    const current = store.get(maybeId);
    if (!current) return { status: 404, body: { message: 'not found' } };
    const updated = stamp({ ...current, ...body, id: maybeId, createdAt: current.createdAt });
    store.set(maybeId, updated);
    return { status: 200, body: updated };
  }
  if (method === 'DELETE' && maybeId) { store.delete(maybeId); return { status: 204, body: undefined }; }
  if (method === 'POST' && !maybeId) {
    if (base === '/governance-evaluations') return createEvaluation(body, state, id);
    if (base === '/decisions') return createDecision(body, state, id);
    if (base === '/execution-authorizations') return issueAuthorization(body, state, id);
    if (base === '/external-execution-results') return createExecutionResult(body, state, id);
    const item = stamp({ id: id(), ...body, status: body?.status ?? defaultStatus(base) });
    store.set(item.id, item);
    return { status: 201, body: item };
  }
  return { status: 405, body: { message: 'method not allowed' } };
}

function createEvaluation(body: any, state: MockState, id: () => string) {
  const intent = state.stores['/intents']!.get(body.intentId);
  const context = state.stores['/operational-contexts']!.get(body.operationalContextId);
  if (!intent || !context) return { status: 422, body: { message: 'intent or context not found' } };
  const item = stamp({ id: id(), ...body, result: 'PENDING', applicableControls: ['AUTHORIZATION_CAP','RESULT_BINDING'], requirements: ['evidence.collection','signed.external.result'] });
  state.stores['/governance-evaluations']!.set(item.id, item);
  return { status: 201, body: item };
}
function createDecision(body: any, state: MockState, id: () => string) {
  const evaluation = state.stores['/governance-evaluations']!.get(body.evaluationId);
  const intent = state.stores['/intents']!.get(body.intentId);
  if (!evaluation || !intent) return { status: 422, body: { message: 'evaluation or intent not found' } };
  const item = stamp({ id: id(), intentId: body.intentId, evaluationId: body.evaluationId, outcome: DecisionOutcome.APPROVED, reasonCodes: ['RESOLVED_REQUIREMENTS_SATISFIED'], authorizationCap: intent.amount ?? 0 });
  state.stores['/decisions']!.set(item.id, item);
  return { status: 201, body: item };
}
function issueAuthorization(body: any, state: MockState, id: () => string) {
  const decision = state.stores['/decisions']!.get(body.decisionId);
  const intent = decision ? state.stores['/intents']!.get(decision.intentId) : undefined;
  if (!decision || !intent) return { status: 422, body: { message: 'decision not found' } };
  const item = stamp({ id: id(), decisionId: decision.id, intentId: intent.id, approvedAmount: decision.authorizationCap, currency: intent.currency ?? 'USD', status: AuthorizationStatus.ISSUED, expiresAt: new Date(Date.now() + 3600_000).toISOString(), bindingHash: hashResultPayload({ decisionId: decision.id, intentId: intent.id, approvedAmount: decision.authorizationCap }) });
  state.stores['/execution-authorizations']!.set(item.id, item);
  return { status: 201, body: item };
}
function createExecutionResult(body: any, state: MockState, id: () => string) {
  const input = normalizeExecutionResult(body);
  const auth = state.stores['/execution-authorizations']!.get(input.authorizationId);
  if (!auth) return { status: 422, body: { message: 'authorization not found' } };
  if (input.amountMinor !== undefined && input.amountMinor > auth.approvedAmount) return { status: 409, body: { message: 'result exceeds authorization cap', code: 'AUTHORIZATION_CAP_EXCEEDED' } };
  if (input.resultPayloadHash !== hashResultPayload(input.resultPayload ?? {})) return { status: 422, body: { message: 'result_payload_hash mismatch', code: 'RESULT_PAYLOAD_HASH_MISMATCH' } };
  if (!verifyResultSignature(input, input.signature, resultSecret)) return { status: 409, body: { message: 'invalid result signature', code: 'RESULT_SIGNATURE_INVALID' } };
  if (!Object.values(ExecutionResultStatus).includes(input.status)) return { status: 422, body: { message: 'invalid execution result status' } };
  const result = stamp({ id: input.executionResultId, ...input });
  state.stores['/external-execution-results']!.set(result.id, result);
  return { status: 201, body: result };
}
function generateProof(resultId: string, state: MockState, id: () => string) {
  const result = state.stores['/external-execution-results']!.get(resultId);
  if (!result) return { status: 422, body: { message: 'result not found' } };
  const auth = state.stores['/execution-authorizations']!.get(result.authorizationId);
  const proof: AIProof = stamp({ id: id(), resultId: result.id, decisionId: auth?.decisionId ?? '', authorizationId: result.authorizationId, resultHash: result.resultPayloadHash, claims: { status: result.status, amountMinor: result.amountMinor, externallyExecuted: true }, signature: proofSignature(result.id, result.resultPayloadHash, result.authorizationId), verificationStatus: VerificationStatus.VERIFIED });
  state.stores['/aiproofs']!.set(proof.id, proof);
  return { status: 201, body: proof };
}
function verifyAuthorizationRoute(body: any, state: MockState, simple = false) {
  const auth = state.stores['/execution-authorizations']!.get(body.id ?? body.authorizationId);
  const valid = Boolean(auth && auth.status !== AuthorizationStatus.REVOKED);
  return { status: 200, body: simple ? { valid } : { valid, authorization: auth } };
}
function verifyProofRoute(state: MockState, id: string) {
  const proof = state.stores['/aiproofs']!.get(id);
  const verified = Boolean(proof && proof.signature === proofSignature(proof.resultId, proof.resultHash, proof.authorizationId));
  return { status: 200, body: { verified, proof } };
}
function verifyProofGeneric(body: any, state: MockState) {
  const proof = body.proofId ? state.stores['/aiproofs']!.get(body.proofId) : body;
  const valid = Boolean(proof && proof.signature === proofSignature(proof.resultId, proof.resultHash, proof.authorizationId));
  return { status: 200, body: { valid } };
}
function verifyBindingRoute(body: any, state: MockState) {
  const result = body.resultId ? state.stores['/external-execution-results']!.get(body.resultId) : body;
  const valid = Boolean(result && result.resultPayloadHash === hashResultPayload(result.resultPayload ?? {}));
  return { status: 200, body: { valid } };
}
function explainDecisionRoute(state: MockState, id: string) {
  const decision = state.stores['/decisions']!.get(id);
  if (!decision) return { status: 404, body: { message: 'not found' } };
  return { status: 200, body: { decision, explanation: 'Decision was produced by the CompliAGL mock server from resolved evaluation data.', reasonCodes: decision.reasonCodes } };
}
function transition(state: MockState, base: string, id: string, patch: Item) {
  const item = state.stores[base]!.get(id);
  if (!item) return { status: 404, body: { message: 'not found' } };
  const updated = stamp({ ...item, ...patch, id, createdAt: item.createdAt });
  state.stores[base]!.set(id, updated);
  return { status: 200, body: updated };
}
function defaultStatus(base: string): string | undefined { return base === '/intents' ? 'CREATED' : undefined; }
function splitResource(path: string): [string, string?] { const parts = path.split('/').filter(Boolean); return [`/${parts[0] ?? ''}`, parts[1]]; }
function stamp<T extends Item>(item: T): T { const now = new Date().toISOString(); return { ...item, createdAt: item.createdAt ?? now, updatedAt: now }; }
function proofSignature(resultId: string, resultHash: string, authorizationId: string): string { return createHmac('sha256', proofSecret).update(canonicalJson({ resultId, resultHash, authorizationId })).digest('hex'); }
function normalizeExecutionResult(body: any) {
  return {
    executionResultId: body.executionResultId ?? body.execution_result_id,
    authorizationId: body.authorizationId ?? body.authorization_id,
    externalSystemId: body.externalSystemId ?? body.external_system_id,
    status: body.status,
    executedAction: body.executedAction ?? body.executed_action,
    target: body.target,
    amountMinor: body.amountMinor ?? body.amount_minor,
    amountCurrency: body.amountCurrency ?? body.amount_currency,
    externalReference: body.externalReference ?? body.external_reference,
    paymentOrSettlementReference: body.paymentOrSettlementReference ?? body.payment_or_settlement_reference,
    resultPayloadHash: body.resultPayloadHash ?? body.result_payload_hash,
    executedAt: body.executedAt ?? body.executed_at,
    submittedAt: body.submittedAt ?? body.submitted_at,
    signerKeyId: body.signerKeyId ?? body.signer_key_id,
    signature: body.signature,
    provenance: body.provenance,
    metadata: body.metadata,
    resultPayload: body.resultPayload ?? body.result_payload,
  };
}
function authorize(req: IncomingMessage, res: ServerResponse): boolean {
  if (req.headers.authorization !== 'Bearer ' + 'test' + '-' + 'key' || req.headers['x-organization-id'] !== 'test-org') { json(res, 401, { message: 'unauthorized' }); return false; }
  return true;
}
function readJson(req: IncomingMessage): Promise<any> { return new Promise((resolve, reject) => { let data=''; req.on('data', c => data += c); req.on('end', () => { try { resolve(data ? JSON.parse(data) : undefined); } catch (e) { reject(e); } }); }); }
function json(res: ServerResponse, status: number, body: unknown, headers: Record<string,string> = {}) { res.writeHead(status, { 'Content-Type': 'application/json', ...headers }); res.end(status === 204 ? undefined : JSON.stringify(body)); }
