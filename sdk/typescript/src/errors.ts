export interface ErrorDetails {
  status?: number;
  code?: string;
  message: string;
  requestId?: string;
  details?: unknown;
}

export class CompliAGLError extends Error {
  readonly status?: number;
  readonly code?: string;
  readonly requestId?: string;
  readonly details?: unknown;

  constructor(details: ErrorDetails) {
    super(details.message);
    this.name = new.target.name;
    this.status = details.status;
    this.code = details.code;
    this.requestId = details.requestId;
    this.details = details.details;
  }
}
export class AuthenticationError extends CompliAGLError {}
export class AuthorizationError extends CompliAGLError {}
export class NotFoundError extends CompliAGLError {}
export class ConflictError extends CompliAGLError {}
export class ValidationError extends CompliAGLError {}
export class RateLimitError extends CompliAGLError {}
export class TimeoutError extends CompliAGLError {}
export class NetworkError extends CompliAGLError {}
export class ServerError extends CompliAGLError {}

export function errorFromResponse(status: number, body: unknown, requestId?: string): CompliAGLError {
  const data = (body && typeof body === 'object') ? body as Record<string, unknown> : {};
  const message = String(data.message ?? data.error ?? `CompliAGL request failed with status ${status}`);
  const code = data.code ? String(data.code) : undefined;
  const details = data.details ?? body;
  const args = { status, code, message, requestId, details };
  if (status === 401) return new AuthenticationError(args);
  if (status === 403) return new AuthorizationError(args);
  if (status === 404) return new NotFoundError(args);
  if (status === 409) return new ConflictError(args);
  if (status === 422 || status === 400) return new ValidationError(args);
  if (status === 429) return new RateLimitError(args);
  if (status >= 500) return new ServerError(args);
  return new CompliAGLError(args);
}
