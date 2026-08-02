export interface RetryConfig {
  retries?: number;
  baseDelayMs?: number;
  maxDelayMs?: number;
  jitter?: boolean;
}

export interface CompliAGLClientConfig {
  baseUrl: string;
  apiKey: string;
  organizationId: string;
  timeoutMs?: number;
  retry?: RetryConfig;
  fetch?: typeof fetch;
}

export interface RequestOptions {
  idempotencyKey?: string;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

export interface NormalizedCompliAGLClientConfig {
  baseUrl: string;
  apiKey: string;
  organizationId: string;
  timeoutMs: number;
  retry: Required<RetryConfig>;
  fetch: typeof fetch;
}

export function normalizeConfig(config: CompliAGLClientConfig): NormalizedCompliAGLClientConfig {
  const f = config.fetch ?? globalThis.fetch;
  if (!f) throw new Error('A fetch implementation is required. Node 18+ provides global fetch.');
  return {
    baseUrl: trimTrailingSlashes(config.baseUrl),
    apiKey: config.apiKey,
    organizationId: config.organizationId,
    timeoutMs: config.timeoutMs ?? 30_000,
    retry: {
      retries: config.retry?.retries ?? 3,
      baseDelayMs: config.retry?.baseDelayMs ?? 250,
      maxDelayMs: config.retry?.maxDelayMs ?? 5_000,
      jitter: config.retry?.jitter ?? true,
    },
    fetch: f,
  };
}

function trimTrailingSlashes(value: string): string {
  let end = value.length;
  while (end > 0 && value.charCodeAt(end - 1) === 47) end--;
  return value.slice(0, end);
}
