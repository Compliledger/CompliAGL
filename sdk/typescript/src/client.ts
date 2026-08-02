import type { CompliAGLClientConfig } from './config';
import { HttpClient } from './http';
import { ActorIdentityClient } from './clients/actorIdentities';
import { IntentClient } from './clients/intents';
import { TargetClient } from './clients/targets';
import { OperationalContextClient } from './clients/operationalContexts';
import { EvaluationClient } from './clients/evaluations';
import { EvidenceClient } from './clients/evidence';
import { DecisionClient } from './clients/decisions';
import { AuthorizationClient } from './clients/authorizations';
import { ExecutionResultClient } from './clients/executionResults';
import { AIProofClient } from './clients/aiproofs';
import { VerificationClient } from './clients/verification';

export class CompliAGLClient {
  readonly http: HttpClient;
  readonly actorIdentities: ActorIdentityClient;
  readonly intents: IntentClient;
  readonly targets: TargetClient;
  readonly operationalContexts: OperationalContextClient;
  readonly evaluations: EvaluationClient;
  readonly evidence: EvidenceClient;
  readonly decisions: DecisionClient;
  readonly authorizations: AuthorizationClient;
  readonly executionResults: ExecutionResultClient;
  readonly aiproofs: AIProofClient;
  readonly verification: VerificationClient;

  constructor(config: CompliAGLClientConfig) {
    this.http = new HttpClient(config);
    this.actorIdentities = new ActorIdentityClient(this.http);
    this.intents = new IntentClient(this.http);
    this.targets = new TargetClient(this.http);
    this.operationalContexts = new OperationalContextClient(this.http);
    this.evaluations = new EvaluationClient(this.http);
    this.evidence = new EvidenceClient(this.http);
    this.decisions = new DecisionClient(this.http);
    this.authorizations = new AuthorizationClient(this.http);
    this.executionResults = new ExecutionResultClient(this.http);
    this.aiproofs = new AIProofClient(this.http);
    this.verification = new VerificationClient(this.http);
  }
}
