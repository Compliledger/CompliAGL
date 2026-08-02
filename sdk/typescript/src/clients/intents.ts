import { CrudClient } from './base';
import type { Intent, CreateIntent } from '../models';
import type { RequestOptions } from '../config';
export class IntentClient extends CrudClient<Intent, CreateIntent> {
  constructor(http: import('../http').HttpClient) { super(http, '/intents'); }
  transition(id: string, input: { status: string; metadata?: Record<string, unknown> }, options?: RequestOptions): Promise<Intent> { return this.http.post<Intent>(`/intents/${encodeURIComponent(id)}/transition`, input, options); }
}
