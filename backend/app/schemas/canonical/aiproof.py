"""Canonical CompliAGL **AIProof** schema — the single governance-lifecycle proof.

An **AIProof** is the verifiable record CompliAGL issues after a *governed
outcome*. It is the one canonical proof implementation for the platform and
supersedes the earlier duplicated proof records (the transaction-scoped
``ProofBundle`` and the demo ``ProofResponse``).

The AIProof supports the complete governance lifecycle:

* approved and executed actions,
* approved but externally failed actions,
* denied actions,
* escalated actions,
* remediated and re-evaluated actions,
* terminated intents.

It stores **references and canonical projections** of the governance chain — not
raw sensitive payloads. Evidence in particular is referenced by id, hash, source
classification, validation outcome and a secure retrieval reference; evidence
payloads and PII are never embedded in the AIProof.

The immutable proof content is canonicalized with RFC 8785 (JCS), hashed with
SHA-256, and the hash is digitally signed. The canonicalization and hash
algorithm identifiers, the issuer, the signer key id and the signature all
travel inside the AIProof so it can be **independently** schema-validated and
signature-verified.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

# The published, versioned AIProof schema version. Bump on any breaking change
# to the canonical AIProof shape.
AIPROOF_SCHEMA_VERSION = "1.0.0"

# The canonical proof type discriminator.
AIPROOF_PROOF_TYPE = "compliagl.aiproof"


# --------------------------------------------------------------------------- #
# Lifecycle vocabularies
# --------------------------------------------------------------------------- #
class AIProofStatus(str, Enum):
    """Lifecycle status of an AIProof envelope.

    The proof *content* is immutable once generated; the status tracks the
    proof's journey from generation through the CompliLedger handoff.
    """

    GENERATED = "GENERATED"
    SIGNED = "SIGNED"
    SUBMITTED_TO_COMPLILEDGER = "SUBMITTED_TO_COMPLILEDGER"
    ACCEPTED_BY_COMPLILEDGER = "ACCEPTED_BY_COMPLILEDGER"
    REJECTED_BY_COMPLILEDGER = "REJECTED_BY_COMPLILEDGER"
    SUPERSEDED = "SUPERSEDED"
    REVOKED = "REVOKED"


class GovernedOutcome(str, Enum):
    """The category of governed outcome an AIProof attests to."""

    APPROVED_AND_EXECUTED = "APPROVED_AND_EXECUTED"
    APPROVED_BUT_EXECUTION_FAILED = "APPROVED_BUT_EXECUTION_FAILED"
    DENIED = "DENIED"
    ESCALATED = "ESCALATED"
    REMEDIATED_AND_REEVALUATED = "REMEDIATED_AND_REEVALUATED"
    TERMINATED = "TERMINATED"


class HandoffStatus(str, Enum):
    """Status of the CompliLedger handoff for an AIProof."""

    PENDING = "PENDING"
    SUBMITTED = "SUBMITTED"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"


# --------------------------------------------------------------------------- #
# Projection sub-models (references + canonical projections, never raw payloads)
# --------------------------------------------------------------------------- #
class _Projection(BaseModel):
    """Base for canonical projection sub-models."""

    model_config = ConfigDict(extra="forbid")


class ProofMetadata(_Projection):
    """(1) Proof metadata."""

    aiproof_id: str
    schema_version: str = AIPROOF_SCHEMA_VERSION
    proof_type: str = AIPROOF_PROOF_TYPE
    organization_id: str
    governance_evaluation_id: Optional[str] = None
    correlation_id: Optional[str] = None
    governed_outcome: GovernedOutcome


class ActorIdentityRef(_Projection):
    """(2) Actor Identity — canonical projection, no secrets."""

    actor_identity_id: str
    actor_type: Optional[str] = None
    credential_type: Optional[str] = None
    verification_status: Optional[str] = None
    revocation_status: Optional[str] = None
    actor_hash: Optional[str] = None


class IntentRef(_Projection):
    """(3) Intent."""

    intent_id: str
    intent_type: Optional[str] = None
    action: Optional[str] = None
    requested_outcome: Optional[str] = None
    amount_minor: Optional[int] = None
    amount_currency: Optional[str] = None
    intent_hash: Optional[str] = None


class TargetRef(_Projection):
    """(4) Target."""

    target_id: Optional[str] = None
    target_type: Optional[str] = None
    classification: Optional[str] = None
    trust_status: Optional[str] = None
    target_hash: Optional[str] = None


class OperationalContextRef(_Projection):
    """(5) Current Operational Context."""

    operational_context_id: Optional[str] = None
    environment: Optional[str] = None
    jurisdiction: Optional[str] = None
    business_unit: Optional[str] = None
    context_hash: Optional[str] = None


class GovernancePackageRef(_Projection):
    """(6) Governance package id + version."""

    package_id: str
    package_name: Optional[str] = None
    package_version: Optional[str] = None
    package_hash: Optional[str] = None


class PolicyResolutionRef(_Projection):
    """(7) Policy Resolution."""

    policy_resolution_id: str
    status: Optional[str] = None
    selected_package_ids: list[str] = Field(default_factory=list)
    engine_version: Optional[str] = None
    result_hash: Optional[str] = None


class ApplicabilityEvaluationRef(_Projection):
    """(8) Applicability Evaluation (per requirement)."""

    applicability_evaluation_id: str
    package_id: Optional[str] = None
    package_version: Optional[str] = None
    requirement_id: Optional[str] = None
    result: Optional[str] = None
    result_hash: Optional[str] = None


class ApplicableControlSetRef(_Projection):
    """(9) Applicable Controls."""

    applicable_control_set_id: str
    control_ids: list[str] = Field(default_factory=list)
    engine_version: Optional[str] = None
    result_hash: Optional[str] = None


class EvidenceRequirementSetRef(_Projection):
    """(10) Evidence Requirements."""

    evidence_requirement_set_id: str
    evidence_requirement_ids: list[str] = Field(default_factory=list)
    engine_version: Optional[str] = None
    result_hash: Optional[str] = None


class EvidenceReference(_Projection):
    """(11) Evidence reference — id, hash, classification, secure retrieval.

    Sensitive payloads and PII are **never** placed here. Only the evidence id,
    hash, source classification, validation outcome and an access-controlled
    secure retrieval reference are recorded.
    """

    evidence_id: str
    evidence_hash: Optional[str] = None
    evidence_type: Optional[str] = None
    source_id: Optional[str] = None
    source_type: Optional[str] = None
    source_classification: Optional[str] = None
    validation_outcome: Optional[str] = None
    secure_retrieval_reference: Optional[str] = None


class EvidenceValidationRef(_Projection):
    """(12) Evidence validation result."""

    evidence_validation_result_id: str
    raw_evidence_id: Optional[str] = None
    evidence_requirement_id: Optional[str] = None
    outcome: Optional[str] = None
    result_hash: Optional[str] = None


class CanonicalEvidencePackageRef(_Projection):
    """(13) Canonical Evidence Package hash."""

    canonical_evidence_package_id: str
    evidence_package_hash: Optional[str] = None


class EvidenceSufficiencyRef(_Projection):
    """(14) Evidence Sufficiency."""

    evidence_sufficiency_id: str
    overall_result: Optional[str] = None
    engine_version: Optional[str] = None
    result_hash: Optional[str] = None


class ControlEvaluationRef(_Projection):
    """(15) Control Evaluation (per control)."""

    control_evaluation_id: str
    control_id: Optional[str] = None
    package_id: Optional[str] = None
    package_version: Optional[str] = None
    control_version: Optional[str] = None
    mandatory: Optional[bool] = None
    result: Optional[str] = None
    result_hash: Optional[str] = None


class AssessmentRef(_Projection):
    """(16) Assessment."""

    assessment_id: str
    overall_result: Optional[str] = None
    engine_version: Optional[str] = None
    assessment_hash: Optional[str] = None


class DecisionRef(_Projection):
    """(17) Deterministic Decision."""

    decision_id: str
    outcome: str
    reason_codes: list[str] = Field(default_factory=list)
    policy_version: Optional[str] = None
    engine_version: Optional[str] = None
    supersession_status: Optional[str] = None
    prior_decision_id: Optional[str] = None
    decision_hash: Optional[str] = None


class FindingRef(_Projection):
    """(18) Finding (where applicable)."""

    finding_id: str
    finding_type: Optional[str] = None
    severity: Optional[str] = None
    status: Optional[str] = None
    decision_impact: Optional[str] = None
    terminal: Optional[bool] = None
    finding_hash: Optional[str] = None


class RemediationLineage(_Projection):
    """(19) Remediation and resolution lineage (where applicable)."""

    remediation_plan_ids: list[str] = Field(default_factory=list)
    resolution_evidence_ids: list[str] = Field(default_factory=list)
    resolved_finding_ids: list[str] = Field(default_factory=list)
    resolved_by_decision_id: Optional[str] = None
    prior_decision_id: Optional[str] = None


class ExecutionAuthorizationRef(_Projection):
    """(20) Execution Authorization (where applicable)."""

    execution_authorization_id: str
    status: Optional[str] = None
    authorized_action: Optional[str] = None
    max_amount_minor: Optional[int] = None
    max_amount_currency: Optional[str] = None
    signer_key_id: Optional[str] = None
    authorization_hash: Optional[str] = None


class ExternalExecutionResultRef(_Projection):
    """(21) External Execution Result (where applicable)."""

    external_execution_result_id: str
    adapter: Optional[str] = None
    status: Optional[str] = None
    external_reference: Optional[str] = None
    settlement_chain: Optional[str] = None
    error: Optional[str] = None


class ProofTimestamps(_Projection):
    """(23) Timestamps."""

    generated_at: str
    context_at: Optional[str] = None
    decided_at: Optional[str] = None
    authorized_at: Optional[str] = None
    executed_at: Optional[str] = None


# --------------------------------------------------------------------------- #
# The canonical AIProof
# --------------------------------------------------------------------------- #

# Envelope fields excluded from the deterministic proof hash. The hash binds the
# immutable proof content; the signature is computed over the hash, and the
# status is mutable envelope metadata.
HASH_EXCLUDED_FIELDS: frozenset[str] = frozenset(
    {"aiproof_hash", "signature", "status"}
)


class AIProof(BaseModel):
    """The single canonical CompliAGL AIProof."""

    model_config = ConfigDict(extra="forbid")

    # Envelope / status (mutable, excluded from the hash).
    status: AIProofStatus = AIProofStatus.GENERATED

    # Canonicalization + hashing self-description.
    canonicalization_algorithm: str
    hash_algorithm: str

    # (1) Proof metadata.
    metadata: ProofMetadata

    # (2)-(5) Actor / Intent / Target / Context.
    actor_identity: ActorIdentityRef
    intent: IntentRef
    target: Optional[TargetRef] = None
    operational_context: Optional[OperationalContextRef] = None

    # (6) Governance packages.
    governance_packages: list[GovernancePackageRef] = Field(default_factory=list)

    # (7) Policy Resolution.
    policy_resolution: Optional[PolicyResolutionRef] = None

    # (8) Applicability Evaluation.
    applicability_evaluations: list[ApplicabilityEvaluationRef] = Field(
        default_factory=list
    )

    # (9) Applicable Controls.
    applicable_controls: Optional[ApplicableControlSetRef] = None

    # (10) Evidence Requirements.
    evidence_requirements: Optional[EvidenceRequirementSetRef] = None

    # (11) Evidence references.
    evidence_references: list[EvidenceReference] = Field(default_factory=list)

    # (12) Evidence validation results.
    evidence_validation_results: list[EvidenceValidationRef] = Field(
        default_factory=list
    )

    # (13) Canonical Evidence Package.
    canonical_evidence_package: Optional[CanonicalEvidencePackageRef] = None

    # (14) Evidence Sufficiency.
    evidence_sufficiency: Optional[EvidenceSufficiencyRef] = None

    # (15) Control Evaluations.
    control_evaluations: list[ControlEvaluationRef] = Field(default_factory=list)

    # (16) Assessment.
    assessment: Optional[AssessmentRef] = None

    # (17) Deterministic Decision.
    decision: DecisionRef

    # (18) Findings.
    findings: list[FindingRef] = Field(default_factory=list)

    # (19) Remediation / resolution lineage.
    remediation_lineage: Optional[RemediationLineage] = None

    # (20) Execution Authorization.
    execution_authorization: Optional[ExecutionAuthorizationRef] = None

    # (21) External Execution Result.
    external_execution_result: Optional[ExternalExecutionResultRef] = None

    # (22) Prior / superseded proof references.
    prior_aiproof_id: Optional[str] = None
    superseded_aiproof_ids: list[str] = Field(default_factory=list)

    # (23) Timestamps.
    timestamps: ProofTimestamps

    # (24) Engine versions (engine name -> version).
    engine_versions: dict[str, str] = Field(default_factory=dict)

    # (25) Component hashes (component name -> canonical hash).
    component_hashes: dict[str, str] = Field(default_factory=dict)

    # (27)-(28) Issuer + signer key id (bound into the hash).
    issuer: str
    signer_key_id: str

    # (26) AIProof hash (excluded from the hash input).
    aiproof_hash: Optional[str] = None

    # (29) Digital signature over the AIProof hash (excluded from the hash input).
    signature: Optional[str] = None

    def hashable_content(self) -> dict[str, Any]:
        """Return the deterministic, hashable view of this proof.

        Envelope fields (:data:`HASH_EXCLUDED_FIELDS`) are removed so the same
        immutable proof always canonicalizes to the same bytes regardless of
        status transitions or signature attachment.
        """
        data = self.model_dump(mode="json")
        for field in HASH_EXCLUDED_FIELDS:
            data.pop(field, None)
        return data


# --------------------------------------------------------------------------- #
# CompliLedger handoff
# --------------------------------------------------------------------------- #
class CompliLedgerProofHandoff(BaseModel):
    """Formal handoff payload delivered to CompliLedger for an AIProof.

    This is the wire contract between CompliAGL and CompliLedger. It carries the
    canonical AIProof together with everything CompliLedger needs to
    independently schema-validate and signature-verify it.
    """

    model_config = ConfigDict(extra="forbid")

    aiproof_id: str
    schema_version: str
    canonical_aiproof: AIProof
    aiproof_hash: str
    signature: str
    signer_identity: str
    signer_key_id: str
    organization_id: str
    requested_proof_policy: Optional[str] = None
    privacy_classification: str
    correlation_id: Optional[str] = None


# --------------------------------------------------------------------------- #
# API request / response models
# --------------------------------------------------------------------------- #
class AIProofGenerateRequest(BaseModel):
    """Request body to generate + sign a canonical AIProof.

    The caller supplies the governance-lifecycle projections; CompliAGL computes
    the component hashes, the canonical AIProof hash, the issuer, the signer key
    id and the signature.
    """

    model_config = ConfigDict(extra="forbid")

    metadata: ProofMetadata
    actor_identity: ActorIdentityRef
    intent: IntentRef
    target: Optional[TargetRef] = None
    operational_context: Optional[OperationalContextRef] = None
    governance_packages: list[GovernancePackageRef] = Field(default_factory=list)
    policy_resolution: Optional[PolicyResolutionRef] = None
    applicability_evaluations: list[ApplicabilityEvaluationRef] = Field(
        default_factory=list
    )
    applicable_controls: Optional[ApplicableControlSetRef] = None
    evidence_requirements: Optional[EvidenceRequirementSetRef] = None
    evidence_references: list[EvidenceReference] = Field(default_factory=list)
    evidence_validation_results: list[EvidenceValidationRef] = Field(
        default_factory=list
    )
    canonical_evidence_package: Optional[CanonicalEvidencePackageRef] = None
    evidence_sufficiency: Optional[EvidenceSufficiencyRef] = None
    control_evaluations: list[ControlEvaluationRef] = Field(default_factory=list)
    assessment: Optional[AssessmentRef] = None
    decision: DecisionRef
    findings: list[FindingRef] = Field(default_factory=list)
    remediation_lineage: Optional[RemediationLineage] = None
    execution_authorization: Optional[ExecutionAuthorizationRef] = None
    external_execution_result: Optional[ExternalExecutionResultRef] = None
    prior_aiproof_id: Optional[str] = None
    superseded_aiproof_ids: list[str] = Field(default_factory=list)
    timestamps: ProofTimestamps
    engine_versions: dict[str, str] = Field(default_factory=dict)
    # Optional handoff hints recorded at submission time (not part of the proof).
    requested_proof_policy: Optional[str] = None
    privacy_classification: Optional[str] = None


class AIProofSubmitRequest(BaseModel):
    """Request body to submit a stored AIProof to CompliLedger."""

    model_config = ConfigDict(extra="forbid")

    requested_proof_policy: Optional[str] = None
    privacy_classification: Optional[str] = None


class AIProofHandoffStatusResponse(BaseModel):
    """Handoff status view for a stored AIProof."""

    aiproof_id: str
    status: str
    handoff_status: str
    handoff_reference: Optional[str] = None
    handoff_detail: Optional[str] = None
    requested_proof_policy: Optional[str] = None
    privacy_classification: Optional[str] = None
    submitted_at: Optional[Any] = None
    handoff_resolved_at: Optional[Any] = None


class AIProofHistoryItem(BaseModel):
    """Compact AIProof summary used in history listings."""

    model_config = ConfigDict(from_attributes=True)

    aiproof_id: str = Field(validation_alias="id")
    organization_id: str
    proof_schema_version: str
    proof_type: str
    governed_outcome: str
    status: str
    handoff_status: str
    aiproof_hash: str
    signer_key_id: str
    issuer: str
    correlation_id: Optional[str] = None
    governance_evaluation_id: Optional[str] = None
    actor_identity_id: Optional[str] = None
    intent_id: Optional[str] = None
    decision_id: Optional[str] = None
    prior_aiproof_id: Optional[str] = None
    created_at: Optional[Any] = None


class AIProofSubmitResponse(BaseModel):
    """Response of a CompliLedger submission."""

    handoff: CompliLedgerProofHandoff
    result_status: str
    handoff_reference: Optional[str] = None
    detail: Optional[str] = None
