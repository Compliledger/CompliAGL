export type ISODateTime = string;
export type ID = string;
export type Metadata = Record<string, unknown>;

export enum ExecutionResultStatus {
  SUCCEEDED = 'SUCCEEDED',
  FAILED = 'FAILED',
  PARTIALLY_COMPLETED = 'PARTIALLY_COMPLETED',
  CANCELLED = 'CANCELLED',
  TIMED_OUT = 'TIMED_OUT',
  REJECTED_BY_EXTERNAL_SYSTEM = 'REJECTED_BY_EXTERNAL_SYSTEM',
}
export enum DecisionOutcome { APPROVED = 'APPROVED', DENIED = 'DENIED', ESCALATED = 'ESCALATED' }
export enum AuthorizationStatus { ISSUED = 'ISSUED', VERIFIED = 'VERIFIED', CONSUMED = 'CONSUMED', REVOKED = 'REVOKED' }
export enum VerificationStatus { VERIFIED = 'VERIFIED', FAILED = 'FAILED' }

export interface Resource { id: ID; createdAt: ISODateTime; updatedAt?: ISODateTime; metadata?: Metadata; }
export interface ActorIdentity extends Resource { externalActorId: string; actorType: string; displayName: string; publicKey?: string; }
export interface Intent extends Resource { actorIdentityId: ID; action: string; targetId?: ID; amount?: number; currency?: string; status: string; payload?: Metadata; }
export interface Target extends Resource { externalTargetId: string; targetType: string; displayName: string; attributes?: Metadata; }
export interface OperationalContext extends Resource { intentId: ID; targetId?: ID; environment: string; facts: Metadata; }
export interface GovernanceEvaluation extends Resource { intentId: ID; operationalContextId: ID; result: string; applicableControls: string[]; requirements: string[]; }
export interface EvidenceCollection extends Resource { evaluationId: ID; status: string; evidenceSourceIds: ID[]; artifacts?: Metadata[]; }
export interface EvidenceSource extends Resource { sourceType: string; uri?: string; payload?: Metadata; }
export interface Decision extends Resource { intentId: ID; evaluationId: ID; outcome: DecisionOutcome; reasonCodes: string[]; authorizationCap?: number; }
export interface ExecutionAuthorization extends Resource { decisionId: ID; intentId: ID; approvedAmount: number; currency: string; status: AuthorizationStatus; expiresAt: ISODateTime; bindingHash: string; }

export interface ExternalExecutionResult extends Resource {
  executionResultId: ID;
  authorizationId: ID;
  externalSystemId: string;
  status: ExecutionResultStatus;
  executedAction: string;
  target: string | Metadata;
  amountMinor?: number;
  amountCurrency?: string;
  externalReference?: string;
  paymentOrSettlementReference?: string;
  resultPayloadHash: string;
  executedAt: ISODateTime;
  submittedAt: ISODateTime;
  signerKeyId: string;
  signature: string;
  provenance: Metadata;
  metadata?: Metadata;
  resultPayload?: Metadata;
}

export interface AIProof extends Resource {
  resultId: ID;
  decisionId: ID;
  authorizationId: ID;
  resultHash: string;
  claims: Metadata;
  signature: string;
  verificationStatus: VerificationStatus;
}

export interface CreateActorIdentity { externalActorId: string; actorType: string; displayName: string; publicKey?: string; metadata?: Metadata; }
export interface CreateIntent { actorIdentityId: ID; action: string; targetId?: ID; amount?: number; currency?: string; payload?: Metadata; metadata?: Metadata; }
export interface CreateTarget { externalTargetId: string; targetType: string; displayName: string; attributes?: Metadata; metadata?: Metadata; }
export interface CreateOperationalContext { intentId: ID; targetId?: ID; environment: string; facts: Metadata; metadata?: Metadata; }
export interface CreateGovernanceEvaluation { intentId: ID; operationalContextId: ID; metadata?: Metadata; }
export interface CreateEvidenceCollection { evaluationId: ID; evidenceSourceIds: ID[]; artifacts?: Metadata[]; metadata?: Metadata; }
export interface CreateEvidenceSource { sourceType: string; uri?: string; payload?: Metadata; metadata?: Metadata; }
export interface CreateDecision { intentId: ID; evaluationId: ID; evidenceCollectionId?: ID; metadata?: Metadata; }
export interface IssueExecutionAuthorization { decisionId: ID; metadata?: Metadata; }
export type CreateExecutionResult = Omit<ExternalExecutionResult, 'id' | 'createdAt' | 'updatedAt'>;
