import { createHmac, timingSafeEqual } from 'node:crypto';

export interface WebhookVerificationOptions {
  secret: string;
  payload: string | Buffer;
  signature: string;
  timestamp: string | number;
  toleranceSeconds?: number;
}

export function signWebhookPayload(secret: string, payload: string | Buffer, timestamp: string | number = Math.floor(Date.now() / 1000)): string {
  return createHmac('sha256', secret).update(`${timestamp}.`).update(payload).digest('hex');
}

export function verifyWebhookSignature(options: WebhookVerificationOptions): boolean {
  const tolerance = options.toleranceSeconds ?? 300;
  const ts = typeof options.timestamp === 'number' ? options.timestamp : Number(options.timestamp);
  if (!Number.isFinite(ts)) return false;
  const now = Math.floor(Date.now() / 1000);
  if (Math.abs(now - ts) > tolerance) return false;
  const expected = Buffer.from(signWebhookPayload(options.secret, options.payload, ts), 'hex');
  const sig = options.signature.startsWith('sha256=') ? options.signature.slice(7) : options.signature;
  let actual: Buffer;
  try { actual = Buffer.from(sig, 'hex'); } catch { return false; }
  return expected.length === actual.length && timingSafeEqual(expected, actual);
}
