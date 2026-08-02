import type { RequestOptions } from '../config';
import type { HttpClient } from '../http';

export class CrudClient<T, C = Partial<T>, U = Partial<C>> {
  constructor(protected readonly http: HttpClient, protected readonly path: string) {}
  list(options?: RequestOptions): Promise<T[]> { return this.http.get<T[]>(this.path, options); }
  get(id: string, options?: RequestOptions): Promise<T> { return this.http.get<T>(`${this.path}/${encodeURIComponent(id)}`, options); }
  create(input: C, options?: RequestOptions): Promise<T> { return this.http.post<T>(this.path, input, options); }
  update(id: string, input: U, options?: RequestOptions): Promise<T> { return this.http.patch<T>(`${this.path}/${encodeURIComponent(id)}`, input, options); }
  delete(id: string, options?: RequestOptions): Promise<void> { return this.http.delete<void>(`${this.path}/${encodeURIComponent(id)}`, options); }
}
