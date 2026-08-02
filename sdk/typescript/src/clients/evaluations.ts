import { CrudClient } from './base';
import type { GovernanceEvaluation, CreateGovernanceEvaluation } from '../models';
import type { RequestOptions } from '../config';
export class EvaluationClient extends CrudClient<GovernanceEvaluation, CreateGovernanceEvaluation> {
  constructor(http: import('../http').HttpClient) { super(http, '/governance-evaluations'); }
  resolve(id: string, input: Record<string, unknown> = {}, options?: RequestOptions): Promise<GovernanceEvaluation> { return this.http.post<GovernanceEvaluation>(`/governance-evaluations/${encodeURIComponent(id)}/resolve`, input, options); }
}
