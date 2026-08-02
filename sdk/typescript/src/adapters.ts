import type { ActorIdentity, AIProof, EvidenceCollection, ExecutionAuthorization, ExternalExecutionResult, Intent } from './models';
export interface AgentIdentityProvider { getIdentity(): Promise<ActorIdentity>; }
export interface EvidenceProvider { collectEvidence(subjectId: string): Promise<EvidenceCollection>; }
export interface ExternalExecutionSystem { execute(authorization: ExecutionAuthorization): Promise<ExternalExecutionResult>; }
export interface MerchantSystem extends ExternalExecutionSystem {
  selectOffer(input?: unknown): Promise<unknown>;
  fulfill(authorization: ExecutionAuthorization): Promise<unknown>;
  createIntent?(input: unknown): Promise<Intent>;
}
export interface PaymentSystem extends ExternalExecutionSystem {
  settle(amount: number, currency: string, metadata?: unknown): Promise<unknown>;
}
export interface HederaAgentAccount { accountId: string; sign(message: Uint8Array): Promise<Uint8Array>; }
export interface ProofVerifier { verifyProof(proof: AIProof): Promise<boolean>; }
