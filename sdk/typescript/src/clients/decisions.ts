import { CrudClient } from './base';
import type { CreateDecision, Decision } from '../models';
import type { RequestOptions } from '../config';
export class DecisionClient extends CrudClient<Decision, CreateDecision> {
  constructor(http: import('../http').HttpClient) { super(http, '/decisions'); }
  decide(input: CreateDecision, options?: RequestOptions): Promise<Decision> { return this.http.post<Decision>('/decisions/decide', input, options); }
  explain(id: string, options?: RequestOptions): Promise<{ decision: Decision; explanation: string; reasonCodes: string[] }> { return this.http.get<{ decision: Decision; explanation: string; reasonCodes: string[] }>(`/decisions/${encodeURIComponent(id)}/explain`, options); }
}
