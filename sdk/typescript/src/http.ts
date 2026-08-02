import { normalizeConfig, type CompliAGLClientConfig, type RequestOptions } from './config';
import { errorFromResponse, NetworkError, TimeoutError } from './errors';

export interface HttpRequestOptions extends RequestOptions {
  body?: unknown;
  query?: Record<string, string | number | boolean | undefined>;
}

export class HttpClient {
  private readonly config: ReturnType<typeof normalizeConfig>;
  constructor(config: CompliAGLClientConfig) { this.config = normalizeConfig(config); }

  async get<T>(path: string, options: HttpRequestOptions = {}): Promise<T> { return this.request<T>('GET', path, options); }
  async post<T>(path: string, body?: unknown, options: HttpRequestOptions = {}): Promise<T> { return this.request<T>('POST', path, { ...options, body }); }
  async put<T>(path: string, body?: unknown, options: HttpRequestOptions = {}): Promise<T> { return this.request<T>('PUT', path, { ...options, body }); }
  async patch<T>(path: string, body?: unknown, options: HttpRequestOptions = {}): Promise<T> { return this.request<T>('PATCH', path, { ...options, body }); }
  async delete<T>(path: string, options: HttpRequestOptions = {}): Promise<T> { return this.request<T>('DELETE', path, options); }

  async request<T>(method: string, path: string, options: HttpRequestOptions = {}): Promise<T> {
    const url = new URL(`${this.config.baseUrl}${path.startsWith('/') ? path : `/${path}`}`);
    for (const [k, v] of Object.entries(options.query ?? {})) if (v !== undefined) url.searchParams.set(k, String(v));
    const headers: Record<string, string> = {
      'Accept': 'application/json',
      'Authorization': 'Bearer ' + this.config.apiKey,
      'X-Organization-Id': this.config.organizationId,
      ...options.headers,
    };
    let body: BodyInit | undefined;
    if (options.body !== undefined) { headers['Content-Type'] = 'application/json'; body = JSON.stringify(options.body); }
    if (options.idempotencyKey) headers['Idempotency-Key'] = options.idempotencyKey;

    const retry = this.config.retry;
    let lastError: unknown;
    for (let attempt = 0; attempt <= retry.retries; attempt++) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), this.config.timeoutMs);
      const onAbort = () => controller.abort();
      options.signal?.addEventListener('abort', onAbort, { once: true });
      try {
        const response = await this.config.fetch(url, { method, headers, body, signal: controller.signal });
        clearTimeout(timeout);
        options.signal?.removeEventListener('abort', onAbort);
        if (response.ok) return await parseResponse<T>(response);
        const parsed = await safeParse(response);
        if (attempt < retry.retries && shouldRetryStatus(response.status)) {
          await sleep(delayForAttempt(attempt, retry.baseDelayMs, retry.maxDelayMs, retry.jitter, response.headers.get('Retry-After')));
          continue;
        }
        throw errorFromResponse(response.status, parsed, response.headers.get('X-Request-Id') ?? undefined);
      } catch (err) {
        clearTimeout(timeout);
        options.signal?.removeEventListener('abort', onAbort);
        if (err instanceof Error && err.name === 'AbortError') lastError = new TimeoutError({ message: `CompliAGL request timed out after ${this.config.timeoutMs}ms` });
        else if (err instanceof TypeError) lastError = new NetworkError({ message: err.message });
        else throw err;
        if (attempt < retry.retries) { await sleep(delayForAttempt(attempt, retry.baseDelayMs, retry.maxDelayMs, retry.jitter)); continue; }
        throw lastError;
      }
    }
    throw lastError instanceof Error ? lastError : new NetworkError({ message: 'CompliAGL request failed' });
  }
}

function shouldRetryStatus(status: number): boolean { return status === 408 || status === 429 || status >= 500; }
async function parseResponse<T>(response: Response): Promise<T> {
  if (response.status === 204) return undefined as T;
  return await response.json() as T;
}
async function safeParse(response: Response): Promise<unknown> { try { return await response.json(); } catch { return await response.text(); } }
function delayForAttempt(attempt: number, base: number, max: number, jitter: boolean, retryAfter?: string | null): number {
  if (retryAfter) {
    const seconds = Number(retryAfter);
    if (Number.isFinite(seconds)) return Math.max(0, seconds * 1000);
    const date = Date.parse(retryAfter);
    if (Number.isFinite(date)) return Math.max(0, date - Date.now());
  }
  const raw = Math.min(max, base * 2 ** attempt);
  return jitter ? Math.floor(raw / 2 + Math.random() * raw / 2) : raw;
}
function sleep(ms: number): Promise<void> { return new Promise(resolve => setTimeout(resolve, ms)); }
