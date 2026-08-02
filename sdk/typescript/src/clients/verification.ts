import type { RequestOptions } from '../config';
import type { HttpClient } from '../http';
import type { AIProof, ExecutionAuthorization, ExternalExecutionResult } from '../models';
export class VerificationClient {
  constructor(private readonly http: HttpClient) {}
  verifyAuthorization(input: { authorizationId: string } | ExecutionAuthorization, options?: RequestOptions): Promise<{ valid: boolean }> { return this.http.post<{ valid: boolean }>('/verification/authorization', input, options); }
  verifyProof(input: { proofId: string } | AIProof, options?: RequestOptions): Promise<{ valid: boolean }> { return this.http.post<{ valid: boolean }>('/verification/proof', input, options); }
  verifyExecutionResultBinding(input: { resultId: string } | ExternalExecutionResult, options?: RequestOptions): Promise<{ valid: boolean }> { return this.http.post<{ valid: boolean }>('/verification/execution-result-binding', input, options); }
}
