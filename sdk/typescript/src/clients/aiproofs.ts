import type { RequestOptions } from '../config';
import type { HttpClient } from '../http';
import type { AIProof } from '../models';
export class AIProofClient {
  constructor(private readonly http: HttpClient) {}
  list(options?: RequestOptions): Promise<AIProof[]> { return this.http.get<AIProof[]>('/aiproofs', options); }
  get(id: string, options?: RequestOptions): Promise<AIProof> { return this.http.get<AIProof>(`/aiproofs/${encodeURIComponent(id)}`, options); }
  generate(input: { resultId: string }, options?: RequestOptions): Promise<AIProof> { return this.http.post<AIProof>('/aiproofs/generate', input, options); }
  verify(id: string, options?: RequestOptions): Promise<{ verified: boolean; proof: AIProof }> { return this.http.post<{ verified: boolean; proof: AIProof }>(`/aiproofs/${encodeURIComponent(id)}/verify`, {}, options); }
}
