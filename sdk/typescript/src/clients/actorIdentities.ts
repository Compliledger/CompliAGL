import { CrudClient } from './base';
import type { ActorIdentity, CreateActorIdentity } from '../models';
export class ActorIdentityClient extends CrudClient<ActorIdentity, CreateActorIdentity> { constructor(http: import('../http').HttpClient) { super(http, '/actor-identities'); } }
