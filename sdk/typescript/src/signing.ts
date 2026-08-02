import { createHmac, createHash, timingSafeEqual } from 'node:crypto';

export type JsonValue = null | boolean | number | string | JsonValue[] | { [key: string]: JsonValue | undefined };

export function canonicalJson(value: unknown): string { return JSON.stringify(normalize(value)); }
function normalize(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(normalize);
  if (value && typeof value === 'object') {
    const out: Record<string, unknown> = {};
    for (const key of Object.keys(value as Record<string, unknown>).sort()) {
      const v = (value as Record<string, unknown>)[key];
      if (v !== undefined) out[key] = normalize(v);
    }
    return out;
  }
  return value;
}
export function sha256Hex(value: string | Buffer): string { return createHash('sha256').update(value).digest('hex'); }
export function hashResultPayload(payload: unknown): string { return sha256Hex(canonicalJson(payload)); }

export interface ResultSignatureInput {
  executionResultId: string;
  authorizationId: string;
  externalSystemId: string;
  status: string;
  executedAction: string;
  target: string | Record<string, unknown>;
  amountMinor?: number;
  amountCurrency?: string;
  externalReference?: string;
  paymentOrSettlementReference?: string;
  resultPayloadHash: string;
  executedAt: string;
  submittedAt: string;
}

export function resultSigningString(input: ResultSignatureInput): string {
  const target = typeof input.target === 'string' ? input.target : canonicalJson(input.target);
  return [
    input.executionResultId,
    input.authorizationId,
    input.externalSystemId,
    input.status,
    input.executedAction,
    target,
    input.amountMinor ?? '',
    input.amountCurrency ?? '',
    input.externalReference ?? '',
    input.paymentOrSettlementReference ?? '',
    input.resultPayloadHash,
    input.executedAt,
    input.submittedAt,
  ].map(String).join('\n');
}
export function signResult(input: ResultSignatureInput, secret: string): string { return createHmac('sha256', secret).update(resultSigningString(input)).digest('hex'); }
export function verifyResultSignature(input: ResultSignatureInput, signature: string, secret: string): boolean {
  let actual: Buffer;
  try { actual = Buffer.from(signature, 'hex'); } catch { return false; }
  const expected = Buffer.from(signResult(input, secret), 'hex');
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}
export function attachResultSignature<T extends Omit<ResultSignatureInput, 'resultPayloadHash'> & { resultPayload?: unknown; signerKeyId: string }>(result: T, secret: string): T & { resultPayloadHash: string; signature: string } {
  const resultPayloadHash = hashResultPayload(result.resultPayload ?? {});
  const signature = signResult({ ...result, resultPayloadHash }, secret);
  return { ...result, resultPayloadHash, signature };
}
