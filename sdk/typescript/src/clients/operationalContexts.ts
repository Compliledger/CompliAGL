import { CrudClient } from './base';
import type { OperationalContext, CreateOperationalContext } from '../models';
export class OperationalContextClient extends CrudClient<OperationalContext, CreateOperationalContext> { constructor(http: import('../http').HttpClient) { super(http, '/operational-contexts'); } }
