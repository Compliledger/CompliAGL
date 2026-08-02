import { CrudClient } from './base';
import type { Target, CreateTarget } from '../models';
export class TargetClient extends CrudClient<Target, CreateTarget> { constructor(http: import('../http').HttpClient) { super(http, '/targets'); } }
