"""Impact analysis — determine which governed records a change affects.

Given a recorded :class:`MonitoringEvent`, impact analysis resolves the change
back to the lifecycle scope it touches (an intent and/or an evaluation) and then
enumerates every affected governed record: the **intents**, **evaluations**,
**decisions**, **authorizations**, **findings**, **AIProofs** and **canonical
proof packages** that were derived from the changed object.

The analysis is read-only and deterministic — it never mutates a record. Its
result is what the re-evaluation job consumes to decide what new immutable
records to produce.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.monitoring_event import MonitoringEvent
from app.repositories.canonical import (
    CanonicalAIProofRepository,
    CanonicalEvidencePackageRepository,
    DecisionRepository,
    ExecutionAuthorizationRepository,
    FindingRepository,
    GovernanceEvaluationRepository,
    IntentRepository,
)

# Affected-object type aliases -> the canonical resolution strategy key.
_INTENT_TYPES = {"intent"}
_EVALUATION_TYPES = {"governanceevaluation", "evaluation", "governance_evaluation"}
_DECISION_TYPES = {"decision"}
_AUTH_TYPES = {"executionauthorization", "authorization", "execution_authorization"}
_FINDING_TYPES = {"finding"}
_RESULT_TYPES = {
    "externalexecutionresult",
    "external_execution_result",
    "executionresult",
}


@dataclass
class ImpactResult:
    """The set of governed records a monitored change affects."""

    monitoring_event_id: str
    change_type: str
    affected_object_type: str
    affected_object_id: str
    intent_id: Optional[str] = None
    evaluation_id: Optional[str] = None
    intents: list[str] = field(default_factory=list)
    evaluations: list[str] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    authorizations: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    aiproofs: list[str] = field(default_factory=list)
    canonical_proof_packages: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not any(
            (
                self.intents,
                self.evaluations,
                self.decisions,
                self.authorizations,
                self.findings,
                self.aiproofs,
                self.canonical_proof_packages,
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "monitoring_event_id": self.monitoring_event_id,
            "change_type": self.change_type,
            "affected_object_type": self.affected_object_type,
            "affected_object_id": self.affected_object_id,
            "intent_id": self.intent_id,
            "evaluation_id": self.evaluation_id,
            "intents": list(self.intents),
            "evaluations": list(self.evaluations),
            "decisions": list(self.decisions),
            "authorizations": list(self.authorizations),
            "findings": list(self.findings),
            "aiproofs": list(self.aiproofs),
            "canonical_proof_packages": list(self.canonical_proof_packages),
            "counts": {
                "intents": len(self.intents),
                "evaluations": len(self.evaluations),
                "decisions": len(self.decisions),
                "authorizations": len(self.authorizations),
                "findings": len(self.findings),
                "aiproofs": len(self.aiproofs),
                "canonical_proof_packages": len(self.canonical_proof_packages),
            },
        }


def _resolve_scope(
    db: Session, organization_id: str, event: MonitoringEvent
) -> tuple[Optional[str], Optional[str]]:
    """Resolve the ``(intent_id, evaluation_id)`` a change is scoped to.

    Explicit scoping references on the event win; otherwise the affected object
    is followed back to its intent / evaluation where that link is unambiguous.
    """
    intent_id = event.intent_id
    evaluation_id = event.evaluation_id
    obj_type = (event.affected_object_type or "").strip().lower()
    obj_id = event.affected_object_id

    if intent_id is None and obj_type in _INTENT_TYPES:
        intent_id = obj_id

    if intent_id is None and obj_type in _DECISION_TYPES:
        decision = DecisionRepository(db).get(organization_id, obj_id)
        if decision is not None:
            intent_id = decision.intent_id
            evaluation_id = evaluation_id or decision.evaluation_id

    if intent_id is None and obj_type in _AUTH_TYPES:
        auth = ExecutionAuthorizationRepository(db).get(organization_id, obj_id)
        if auth is not None:
            intent_id = auth.intent_id

    if intent_id is None and obj_type in _FINDING_TYPES:
        finding = FindingRepository(db).get(organization_id, obj_id)
        if finding is None:
            finding = FindingRepository(db).get_by_finding_id(
                organization_id, obj_id
            )
        if finding is not None:
            intent_id = finding.intent_id
            evaluation_id = evaluation_id or finding.evaluation_id

    if intent_id is None and obj_type in _RESULT_TYPES:
        from app.repositories.canonical import (
            ExternalExecutionResultRepository,
        )

        result = ExternalExecutionResultRepository(db).get(
            organization_id, obj_id
        )
        if result is not None:
            intent_id = result.intent_id

    if (intent_id is None) and obj_type in _EVALUATION_TYPES:
        evaluation_id = evaluation_id or obj_id
        evaluation = GovernanceEvaluationRepository(db).get(
            organization_id, obj_id
        )
        if evaluation is not None:
            intent_id = evaluation.intent_id

    return intent_id, evaluation_id


def _unique(values) -> list[str]:
    seen: dict[str, None] = {}
    for value in values:
        if value and value not in seen:
            seen[value] = None
    return list(seen.keys())


def analyze(
    db: Session, organization_id: str, event: MonitoringEvent
) -> ImpactResult:
    """Return the :class:`ImpactResult` for a recorded monitoring event."""
    intent_id, evaluation_id = _resolve_scope(db, organization_id, event)

    result = ImpactResult(
        monitoring_event_id=event.id,
        change_type=event.change_type,
        affected_object_type=event.affected_object_type,
        affected_object_id=event.affected_object_id,
        intent_id=intent_id,
        evaluation_id=evaluation_id,
    )

    evaluation_ids: list[str] = []

    if intent_id is not None:
        intent = IntentRepository(db).get(organization_id, intent_id)
        if intent is not None:
            result.intents = [intent_id]

        evaluations = GovernanceEvaluationRepository(db).list_for_intent(
            organization_id, intent_id
        )
        evaluation_ids.extend(e.id for e in evaluations)

        decisions = DecisionRepository(db).list_for_intent(
            organization_id, intent_id
        )
        result.decisions = [d.id for d in decisions]
        evaluation_ids.extend(
            d.evaluation_id for d in decisions if d.evaluation_id
        )

        authorizations = ExecutionAuthorizationRepository(db).list_for_intent(
            organization_id, intent_id
        )
        result.authorizations = [a.id for a in authorizations]

        findings = FindingRepository(db).list_filtered(
            organization_id, intent_id=intent_id
        )
        result.findings = [f.id for f in findings]

        proofs = CanonicalAIProofRepository(db).list_by(
            organization_id, intent_id=intent_id
        )
        result.aiproofs = [p.id for p in proofs]

    if evaluation_id is not None:
        evaluation_ids.append(evaluation_id)

    result.evaluations = _unique(evaluation_ids)

    package_ids: list[str] = []
    pkg_repo = CanonicalEvidencePackageRepository(db)
    for eval_id in result.evaluations:
        package_ids.extend(
            pkg.id for pkg in pkg_repo.list_for_evaluation(organization_id, eval_id)
        )
    result.canonical_proof_packages = _unique(package_ids)

    return result
