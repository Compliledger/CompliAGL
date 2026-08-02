import { CrudClient } from './base';
import type { ExecutionAuthorization, IssueExecutionAuthorization } from '../models';
import type { RequestOptions } from '../config';
export class AuthorizationClient extends CrudClient<ExecutionAuthorization, IssueExecutionAuthorization> {
  constructor(http: import('../http').HttpClient) { super(http, '/execution-authorizations'); }
  issue(input: IssueExecutionAuthorization, options?: RequestOptions): Promise<ExecutionAuthorization> { return this.http.post<ExecutionAuthorization>('/execution-authorizations/issue', input, options); }
  verify(id: string, options?: RequestOptions): Promise<{ valid: boolean; authorization: ExecutionAuthorization }> { return this.http.post<{ valid: boolean; authorization: ExecutionAuthorization }>('/execution-authorizations/verify', { id }, options); }
  consume(id: string, options?: RequestOptions): Promise<ExecutionAuthorization> { return this.http.post<ExecutionAuthorization>('/execution-authorizations/consume', { id }, options); }
  revoke(id: string, reason?: string, options?: RequestOptions): Promise<ExecutionAuthorization> { return this.http.post<ExecutionAuthorization>('/execution-authorizations/revoke', { id, reason }, options); }
  transition(id: string, status: string, options?: RequestOptions): Promise<ExecutionAuthorization> { return this.http.post<ExecutionAuthorization>('/execution-authorizations/transition', { id, status }, options); }
}
