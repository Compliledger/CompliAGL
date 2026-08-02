# CompliAGL AIProof — Canonical Governance Proof

The **AIProof** is the single canonical, verifiable record CompliAGL issues after
a *governed outcome*. It replaces the earlier duplicated proof records (the
transaction-scoped `ProofBundle` and the demo `ProofResponse` / x402
`AIProofBundle`).

* Schema (Pydantic): `app/schemas/canonical/aiproof.py`
* Subsystem: `app/services/canonical/aiproof/`
* Persistence: `app/models/canonical_aiproof.py` (`canonical_ai_proofs` table)
* Published JSON Schema: [`docs/schemas/aiproof-1.0.0.schema.json`](../schemas/aiproof-1.0.0.schema.json)

## Lifecycle coverage

A single AIProof shape attests to any governed outcome via
`metadata.governed_outcome`:

`APPROVED_AND_EXECUTED`, `APPROVED_BUT_EXECUTION_FAILED`, `DENIED`, `ESCALATED`,
`REMEDIATED_AND_REEVALUATED`, `TERMINATED`.

## Contents (references and canonical projections)

The AIProof carries references / canonical projections for the whole governance
chain: proof metadata, actor identity, intent, target, operational context,
governance package IDs + versions, policy resolution, applicability evaluation,
applicable controls, evidence requirements, evidence references, evidence
validation results, the canonical evidence package hash, evidence sufficiency,
control evaluations, assessment, the deterministic decision, findings,
remediation/resolution lineage, execution authorization, external execution
result, prior/superseded proof references, timestamps, engine versions, component
hashes, the AIProof hash, issuer, signer key id and the digital signature.

### Evidence is referenced, never embedded

Sensitive evidence payloads and PII are **never** placed in an AIProof. Each
`EvidenceReference` stores only the evidence id, evidence hash, source
classification, validation outcome and an access-controlled
`secure_retrieval_reference`.

## Canonicalization, hashing and signing

* **Canonicalization:** RFC 8785 JSON Canonicalization Scheme (JCS). The
  algorithm identifier `JCS/RFC8785` is recorded in every AIProof
  (`canonicalization_algorithm`).
* **Hashing:** SHA-256. The identifier `SHA-256` is recorded
  (`hash_algorithm`). A per-component hash is computed for each projection
  (`component_hashes`) and the top-level `aiproof_hash` is the SHA-256 of the
  canonical proof content (excluding the mutable envelope: `aiproof_hash`,
  `signature`, `status`).
* **Signing:** the `aiproof_hash` is digitally signed. The default signer is an
  environment-backed HMAC-SHA256 implementation
  (`app/services/canonical/aiproof/signing.py`); it is swappable for an
  asymmetric signer without changing callers. `issuer`, `signer_key_id` and
  `signature` travel inside the proof.

An AIProof can therefore be **independently** schema-validated (against the
published JSON Schema) and signature-verified with no other CompliAGL state.

## Statuses

`GENERATED` → `SIGNED` → `SUBMITTED_TO_COMPLILEDGER` →
`ACCEPTED_BY_COMPLILEDGER` / `REJECTED_BY_COMPLILEDGER`; plus `SUPERSEDED` and
`REVOKED`.

## CompliLedger handoff

`CompliLedgerProofHandoff` (`app/schemas/canonical/aiproof.py`) is the formal
handoff payload: AIProof ID, schema version, canonical AIProof, AIProof hash,
signature, signer identity, organization ID, requested proof policy, privacy
classification and correlation ID. The transport interface `CompliLedgerHandoff`
(`app/services/canonical/aiproof/handoff.py`) is swappable; the default
`LocalCompliLedgerHandoff` independently verifies a proof before accepting it.

## APIs (`/api/v1/aiproofs`)

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/aiproofs` | Generate + sign + persist an AIProof |
| `GET` | `/aiproofs/{id}` | Retrieve an AIProof |
| `POST` | `/aiproofs/{id}/verify` | Verify an AIProof locally |
| `POST` | `/aiproofs/{id}/submit` | Submit an AIProof to CompliLedger |
| `GET` | `/aiproofs/{id}/handoff` | Retrieve handoff status |
| `GET` | `/aiproofs/history` | Retrieve AIProof history (filterable) |
| `GET` | `/aiproofs/schema` | Published, versioned AIProof JSON Schema |
