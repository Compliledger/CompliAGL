"""Seed one real HarborStone AML case for the Demo #3 18-step rehearsal.

Unlike ``demo3_step2/compliagl_scenarios.py`` (which forces its own
throwaway local SQLite database and deletes it on every run), this script
does **not** touch ``DATABASE_URL`` and does **not** delete anything. It
runs the same real service pipeline against whatever database is already
configured in the environment -- which, when run from the Railway console
on the CompliAGL service, is the live production Postgres instance.

It creates exactly one real, connected chain of canonical records for case
``HARBORSTONE-2024-0042``:

    Target (case)
      -> Intent  (AIRA proposes a $250,000 transfer, counterparty wallet_002)
      -> OperationalContext
      -> PolicyResolution
      -> ApplicabilityEvaluation
      -> EvidenceCollection (via the REAL default_production_registry(),
         which includes the real harborstone_sentry_screening connector --
         wallet_002 is seeded POTENTIAL_MATCH in that connector's demo
         dataset, so this exercises the human-review escalation path)
      -> EvidenceSufficiency
      -> ControlEvaluation
      -> Assessment
      -> Decision

This is what makes ``get_case_data`` / ``get_authorized_transaction_history``
return real content for case ``HARBORSTONE-2024-0042`` instead of empty
sections, and what step 3 of the 18-step rehearsal (a real SENTRY screening
call) has real evidence to produce.

Run locally (from repo root):

    python seed_rehearsal_case.py

Run from the Railway console (CompliAGL service), from /app:

    /app/.venv/bin/python seed_rehearsal_case.py

Idempotency: this script does NOT check whether the case already exists.
Running it twice creates two Intents for the same case_id. That's fine for
inspection (get_case_data aggregates across all matching intents) but if
you want a clean single-decision case, only run it once, or extend this
script with an existence check before re-running.
"""
from __future__ import annotations

import logging
import os
import sys

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(_REPO_ROOT, "backend")
if _BACKEND not in sys.path:
    sys.path.insert(0, _BACKEND)

logging.disable(logging.WARNING)

import app.db.init_db  # noqa: E402,F401 -- side effect: registers every model on Base.metadata

from app.core.database import SessionLocal  # noqa: E402
from app.db.seed import (  # noqa: E402
    HARBORSTONE_AIRA_ACTOR_ID,
    HARBORSTONE_ORG_ID,
)
from app.schemas.canonical.intent import IntentCreate  # noqa: E402
from app.schemas.canonical.operational_context import (  # noqa: E402
    OperationalContextCreate,
)
from app.schemas.canonical.policy_applicability import (  # noqa: E402
    ApplicabilityEvaluationCreate,
    PolicyResolutionCreate,
)
from app.schemas.canonical.target import TargetCreate  # noqa: E402
from app.services.canonical import (  # noqa: E402
    applicability_service,
    assessment_service,
    control_evaluation_service,
    decision_service,
    evidence_sufficiency_service,
    intent_service,
    operational_context_service,
    policy_resolution_service,
    target_service,
)
from app.services.evidence import evidence_collection_service  # noqa: E402
from app.services.evidence.connectors.production import (  # noqa: E402
    default_production_registry,
)
from app.utils.canonical_enums import IntentType, TargetType  # noqa: E402

CASE = "HARBORSTONE-2024-0042"
COUNTERPARTY_WALLET = "wallet_002"  # seeded POTENTIAL_MATCH in the demo dataset
AMOUNT_MINOR = 25_000_000  # $250,000.00


def main() -> None:
    db = SessionLocal()
    try:
        target = target_service.create(
            db,
            TargetCreate(
                organization_id=HARBORSTONE_ORG_ID,
                target_type=TargetType.TRANSACTION,
                external_identifier=COUNTERPARTY_WALLET,
            ),
        )
        print(f"target created: {target.id}")

        intent = intent_service.create(
            db,
            IntentCreate(
                organization_id=HARBORSTONE_ORG_ID,
                intent_type=IntentType.TRANSFER,
                action="propose_transfer",
                actor_id=HARBORSTONE_AIRA_ACTOR_ID,
                amount_minor=AMOUNT_MINOR,
                amount_currency="USD",
                parameters={
                    "compliidentity_resource": "aml.action",
                    "compliidentity_action": "propose",
                    "compliidentity_resource_instance": CASE,
                    "counterparty": COUNTERPARTY_WALLET,
                },
            ),
        )
        print(f"intent created: {intent.id}")

        context = operational_context_service.create(
            db,
            OperationalContextCreate(
                organization_id=HARBORSTONE_ORG_ID,
                jurisdiction="US",
                environment="STAGING",
            ),
        )
        print(f"operational context created: {context.id}")

        resolution = policy_resolution_service.resolve(
            db,
            PolicyResolutionCreate(
                organization_id=HARBORSTONE_ORG_ID,
                actor_identity_id=HARBORSTONE_AIRA_ACTOR_ID,
                intent_id=intent.id,
                target_id=target.id,
                operational_context_id=context.id,
            ),
        )
        print(f"policy resolution created: {resolution.id}")

        applicability_service.evaluate_for_resolution(
            db,
            ApplicabilityEvaluationCreate(
                organization_id=HARBORSTONE_ORG_ID,
                policy_resolution_id=resolution.id,
            ),
        )
        print("applicability evaluated")

        evidence_collection_service.start_collection(
            db,
            HARBORSTONE_ORG_ID,
            resolution.id,
            production_mode=True,
            registry=default_production_registry(),
        )
        print("evidence collection started (real production registry)")

        evidence_sufficiency_service.evaluate_for_resolution(
            db, HARBORSTONE_ORG_ID, resolution.id
        )
        print("evidence sufficiency evaluated")

        control_evaluation_service.evaluate_for_resolution(
            db, HARBORSTONE_ORG_ID, resolution.id
        )
        print("controls evaluated")

        assessment = assessment_service.assess_for_resolution(
            db, HARBORSTONE_ORG_ID, resolution.id
        )
        print(f"assessment: {assessment.overall_result}")

        decision = decision_service.decide_for_resolution(
            db, HARBORSTONE_ORG_ID, resolution.id
        )
        print(f"decision: {decision.outcome} (decision_id={decision.id})")

        db.commit()
        print("\nDONE -- committed. Case", CASE, "now has real seeded data.")
    except Exception:
        db.rollback()
        print("\nFAILED -- rolled back. See traceback below.", file=sys.stderr)
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()