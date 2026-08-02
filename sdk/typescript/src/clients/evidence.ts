import type { RequestOptions } from '../config';
import type { HttpClient } from '../http';
import type { CreateEvidenceCollection, CreateEvidenceSource, EvidenceCollection, EvidenceSource } from '../models';
export class EvidenceClient {
  constructor(private readonly http: HttpClient) {}
  listCollections(options?: RequestOptions): Promise<EvidenceCollection[]> { return this.http.get<EvidenceCollection[]>('/evidence-collections', options); }
  getCollection(id: string, options?: RequestOptions): Promise<EvidenceCollection> { return this.http.get<EvidenceCollection>(`/evidence-collections/${encodeURIComponent(id)}`, options); }
  createCollection(input: CreateEvidenceCollection, options?: RequestOptions): Promise<EvidenceCollection> { return this.http.post<EvidenceCollection>('/evidence-collections', input, options); }
  listSources(options?: RequestOptions): Promise<EvidenceSource[]> { return this.http.get<EvidenceSource[]>('/evidence-sources', options); }
  getSource(id: string, options?: RequestOptions): Promise<EvidenceSource> { return this.http.get<EvidenceSource>(`/evidence-sources/${encodeURIComponent(id)}`, options); }
  createSource(input: CreateEvidenceSource, options?: RequestOptions): Promise<EvidenceSource> { return this.http.post<EvidenceSource>('/evidence-sources', input, options); }
}
