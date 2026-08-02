import { CrudClient } from './base';
import type { CreateExecutionResult, ExternalExecutionResult } from '../models';
import type { RequestOptions } from '../config';
export class ExecutionResultClient extends CrudClient<ExternalExecutionResult, CreateExecutionResult> {
  constructor(http: import('../http').HttpClient) { super(http, '/external-execution-results'); }
  override create(input: CreateExecutionResult, options?: RequestOptions): Promise<ExternalExecutionResult> { return this.http.post<ExternalExecutionResult>(this.path, toWire(input), options); }
  submit(input: CreateExecutionResult, options?: RequestOptions): Promise<ExternalExecutionResult> { return this.create(input, options); }
}
function toWire(input: CreateExecutionResult): Record<string, unknown> {
  return {
    execution_result_id: input.executionResultId,
    authorization_id: input.authorizationId,
    external_system_id: input.externalSystemId,
    status: input.status,
    executed_action: input.executedAction,
    target: input.target,
    amount_minor: input.amountMinor,
    amount_currency: input.amountCurrency,
    external_reference: input.externalReference,
    payment_or_settlement_reference: input.paymentOrSettlementReference,
    result_payload_hash: input.resultPayloadHash,
    executed_at: input.executedAt,
    submitted_at: input.submittedAt,
    signer_key_id: input.signerKeyId,
    signature: input.signature,
    provenance: input.provenance,
    metadata: input.metadata,
    result_payload: input.resultPayload,
  };
}
