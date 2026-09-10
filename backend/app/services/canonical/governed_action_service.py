"""Governed-action orchestration -- the intent -> decision pipeline as one call.

Productizes the sequence that ``demo3_step2/compliagl_scenarios.py::run_pipeline``
stitches together by hand: create the intent + target + operational context,
resolve policy, evaluate applicability, collect + validate + normalize evidence,
and produce the deterministic :class:`~app.models.decision.Decision` (with the
live CompliIdentity authority probe when the governing package opts in via
``requires_authority_context``).

This is only the "CompliIdentity -> CompliAGL decision" half of the flow.
Everything after it stays an explicit, separate step:

* human approval of an ``ESCALATED`` decision goes through
  ``escalation_approval_service.submit`` + ``decision_service.decide_for_resolution
  (prior_decision_id=)``;
* issuing an ``ExecutionAuthorization`` for an ``APPROVED`` decision goes through
  ``authorization_service.issue``.

This service never auto-approves and never auto-authorizes. It is deliberately
side-effect-symmetric with the demo driver so the two cannot drift.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy.orm import Session

from app.models.assessment import Assessment
from app.models.decision import Decision
from app.models.intent import Intent
from app.models.policy_resolution import PolicyResolution
from app.schemas.canonical.intent import IntentCreate
from app.schemas.canonical.operational_context import OperationalContextCreate
from app.schemas.canonical.policy_applicability import (
    ApplicabilityEvaluationCreate,
    PolicyResolutionCreate,
)
from app.schemas.canonical.target import TargetCreate
from app.services.canonical import (
    applicability_service,
    assessment_service,
    decision_service,
    intent_service,
    operational_context_service,
    policy_resolution_service,
    target_service,
)
from app.services.evidence import evidence_collection_service
from app.services.evidence.connectors import ConnectorRegistry
from app.services.evidence.connectors.production import (
    default_production_registry,
)
from app.utils.canonical_enums import (
    EnvironmentType,
    IntentType,
    TargetType,
)


@dataclass
class GovernedActionResult:
    """Every artifact produced by one ``propose`` run."""

    intent: Intent
    policy_resolution: PolicyResolution
    assessment: Optional[Assessment]
    decision: Decision


def propose(
    db: Session,
    organization_id: str,
    *,
    actor_id: str,
    intent_type: IntentType,
    action: str,
    compliidentity_resource: str,
    compliidentity_action: str,
    resource_instance: str,
    target_identifier: Optional[str] = None,
    rationale: Optional[str] = None,
    amount_minor: Optional[int] = None,
    amount_currency: Optional[str] = None,
    target_type: TargetType = TargetType.TRANSACTION,
    jurisdiction: str = "US",
    environment: EnvironmentType = EnvironmentType.STAGING,
    extra_parameters: Optional[dict[str, Any]] = None,
    correlation_id: Optional[str] = None,
    production_mode: bool = True,
    registry: Optional[ConnectorRegistry] = None,
) -> GovernedActionResult:
    """Run the full canonical intent -> decision pipeline for one proposed action.

    ``compliidentity_resource`` / ``compliidentity_action`` /
    ``resource_instance`` are written into ``intent.parameters`` under the keys
    ``decision_service._authority_request_params`` reads
    (``compliidentity_resource`` / ``compliidentity_action`` /
    ``compliidentity_resource_instance``), so the CompliIdentity authority probe
    and the package's own decision conditions reason about the same action.

    ``target_identifier`` is the subject the action acts on -- a transfer
    destination / counterparty. It becomes the ``Target.external_identifier``,
    which is what the HarborStone package's sanctions-screening requirement
    screens (``subject_binding: "target"``). It defaults to ``resource_instance``
    (the case) when the action has no distinct subject.

    ``decide_for_resolution`` re-runs evidence sufficiency, control evaluation
    and assessment itself (dedup-on-input-hash upstream), so this function does
    not call them separately -- the returned ``assessment`` is the one that
    decision consumed, read back via ``latest_for_resolution``.
    """
    org = organization_id
    if amount_minor is not None and not amount_currency:
        amount_currency = "USD"

    parameters: dict[str, Any] = {
        "compliidentity_resource": compliidentity_resource,
        "compliidentity_action": compliidentity_action,
        "compliidentity_resource_instance": resource_instance,
    }
    if rationale:
        parameters["rationale"] = rationale
    if extra_parameters:
        parameters.update(extra_parameters)

    intent = intent_service.create(
        db,
        IntentCreate(
            organization_id=org,
            intent_type=intent_type,
            action=action,
            actor_id=actor_id,
            requested_outcome=rationale,
            amount_minor=amount_minor,
            amount_currency=amount_currency,
            correlation_id=correlation_id,
            parameters=parameters,
        ),
    )
    target = target_service.create(
        db,
        TargetCreate(
            organization_id=org,
            target_type=target_type,
            external_identifier=target_identifier or resource_instance,
        ),
    )
    op_context = operational_context_service.create(
        db,
        OperationalContextCreate(
            organization_id=org,
            jurisdiction=jurisdiction,
            environment=environment,
        ),
    )
    resolution = policy_resolution_service.resolve(
        db,
        PolicyResolutionCreate(
            organization_id=org,
            actor_identity_id=actor_id,
            intent_id=intent.id,
            target_id=target.id,
            operational_context_id=op_context.id,
        ),
    )
    applicability_service.evaluate_for_resolution(
        db,
        ApplicabilityEvaluationCreate(
            organization_id=org, policy_resolution_id=resolution.id
        ),
    )
    evidence_collection_service.start_collection(
        db,
        org,
        resolution.id,
        production_mode=production_mode,
        registry=registry or default_production_registry(),
    )
    decision = decision_service.decide_for_resolution(db, org, resolution.id)
    assessment = assessment_service.latest_for_resolution(db, org, resolution.id)
    return GovernedActionResult(
        intent=intent,
        policy_resolution=resolution,
        assessment=assessment,
        decision=decision,
    )
