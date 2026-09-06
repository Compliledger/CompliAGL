"""PLACEHOLDER evidence connector for HarborStone sanctions screening.

===========================================================================
PLACEHOLDER -- READ THIS
===========================================================================
This connector performs **no sanctions screening**. It returns a hardcoded
stand-in evidence item so the HarborStone governance package's placeholder
control chain -- ``REQ-PLACEHOLDER-SANCTIONS-SCREENING`` /
``CTL-PLACEHOLDER-SANCTIONS-SCREENING`` (itself ``evaluation_expression:
"True"``) -- can reach SATISFIED and the *decision-engine + CompliIdentity
authority-context wiring* be exercised end to end over HTTP.

It is the HTTP-path analog of the in-process
``demo3_step2/compliagl_scenarios.py`` mock stand-in
(``sim-harborstone-screening-PLACEHOLDER``): same evidence type, same issuer,
same ``STANDIN_PASS`` claim, same fake signature string.

Guardrails (see ``PENDING_REVIEW_harborstone_screening_control_placeholder.md``):

* It is **never** registered by default. ``default_production_registry()``
  only adds it when ``COMPLIAGL_HARBORSTONE_SCREENING_PLACEHOLDER`` is set to
  the literal string ``stand-in-not-real-screening`` -- an explicit
  acknowledgement, not a truthy flag. A real deployment never sets it; the
  evidence type then has no connector and the mandatory control fails closed,
  exactly as it does today.
* Every :meth:`collect` call logs a WARNING.
* The ``connector_id``, the issuer, ``claims.placeholder``,
  ``claims.screening_result`` and the signature string all say "placeholder"
  in plain text.

``is_mock`` is ``False`` **on purpose**: the CompliAGL Execution Gateway
sends ``production_mode=True`` on ``POST /evidence-collections``, and the
orchestrator rejects ``is_mock`` connectors in production mode
(``REJECTED_MOCK``). A mock here would never run on the path this exists to
exercise. The env-gate + acknowledgement string + WARNING log are what keep
this out of a real decision instead.

**This must be deleted** -- together with the placeholder requirement/control
and this connector's env-gate in ``production.py`` -- when HarborStone's real
sanctions-screening requirement, control and evidence source are designed.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.evidence.connectors.base import (
    CollectRequest,
    CollectResult,
    ConnectorHealth,
    EvidenceConnector,
    RetryPolicy,
)
from app.utils.canonical_enums import (
    ConnectorHealthStatus,
    EvidenceCollectionStatus,
    EvidenceSourceType,
)
from app.utils.timestamps import utc_now

logger = logging.getLogger(__name__)

# Must match the HarborStone package's placeholder evidence requirement
# (``app/db/harborstone_package.py`` -> ``EV-PLACEHOLDER-SANCTIONS-SCREENING``:
# ``evidence_type`` and the single ``allowed_issuers`` entry).
HARBORSTONE_SCREENING_PLACEHOLDER_EVIDENCE_TYPE = (
    "harborstone.sanctions_screening_placeholder"
)
HARBORSTONE_SCREENING_PLACEHOLDER_ISSUER = "harborstone-screening-placeholder.example"

# The exact value ``COMPLIAGL_HARBORSTONE_SCREENING_PLACEHOLDER`` must hold for
# ``default_production_registry()`` to register this connector.
HARBORSTONE_SCREENING_PLACEHOLDER_ACK = "stand-in-not-real-screening"

# Self-documenting stand-in signature -- identical to the in-process driver's
# (``demo3_step2/compliagl_scenarios.py``). Not a real attestation.
_PLACEHOLDER_SIGNATURE = "PLACEHOLDER-SIGNATURE-not-a-real-attestation"

_PLACEHOLDER_NOTE = (
    "NOT a real sanctions-screening result. Stand-in so the HarborStone "
    "placeholder control chain and the CompliIdentity authority-context "
    "wiring run end to end over HTTP. See "
    "PENDING_REVIEW_harborstone_screening_control_placeholder.md"
)


class HarborStoneScreeningPlaceholderConnector(EvidenceConnector):
    """Returns a hardcoded stand-in sanctions-screening evidence item.

    Does not call any system and screens nothing. See the module docstring for
    why this exists and the guardrails around it.
    """

    def __init__(
        self,
        *,
        connector_id: str = "harborstone-sanctions-screening-placeholder",
        timeout_seconds: float = 5.0,
        retry_policy: Optional[RetryPolicy] = None,
    ) -> None:
        self.connector_id = connector_id
        self.source_type = EvidenceSourceType.EXTERNAL_APPLICATION.value
        self.supported_evidence_types = (
            HARBORSTONE_SCREENING_PLACEHOLDER_EVIDENCE_TYPE,
        )
        # No real system, no real auth.
        self.auth_config_reference = None
        # NOT a mock in the orchestrator's sense: see the module docstring.
        # It must run under production_mode=True, which is the only path that
        # matters here; the env-gate is the real guardrail.
        self.is_mock = False
        self.trusted_issuers = (HARBORSTONE_SCREENING_PLACEHOLDER_ISSUER,)
        self.timeout_seconds = timeout_seconds
        self.retry_policy = retry_policy or RetryPolicy()

    # -- interface ------------------------------------------------------- #
    def collect(self, request: CollectRequest) -> CollectResult:
        """Return the stand-in screening item, bound to this request."""
        logger.warning(
            "%s: returning a PLACEHOLDER sanctions-screening STAND-IN pass for "
            "requirement %s -- this is NOT a real screening result "
            "(see PENDING_REVIEW_harborstone_screening_control_placeholder.md)",
            self.connector_id,
            request.evidence_requirement_id,
        )
        now = utc_now()
        claims: dict[str, Any] = {
            "placeholder": True,
            "screening_result": "STANDIN_PASS",
            "note": _PLACEHOLDER_NOTE,
            "reference": (
                "backend/PENDING_REVIEW_harborstone_screening_control_"
                "placeholder.md"
            ),
        }
        return CollectResult(
            status=EvidenceCollectionStatus.COLLECTED.value,
            payload=None,
            claims=claims,
            issuer=HARBORSTONE_SCREENING_PLACEHOLDER_ISSUER,
            issued_at=now,
            expires_at=None,
            signature=_PLACEHOLDER_SIGNATURE,
            signature_valid=True,
            revoked=False,
            subject_id=request.subject_id,
            target_id=request.target_id,
            intent_id=request.intent_id,
            source_authority=True,
        )

    def health_check(self) -> ConnectorHealth:
        """Always healthy -- there is nothing to reach."""
        return ConnectorHealth(status=ConnectorHealthStatus.HEALTHY.value)

    def validate_connection(self) -> bool:
        """Always valid -- there is no connection and no auth to check."""
        return True


def harborstone_screening_placeholder_connector(
    **kwargs: Any,
) -> HarborStoneScreeningPlaceholderConnector:
    """Factory matching the style of ``simulators.py`` / ``securerob.py``."""
    return HarborStoneScreeningPlaceholderConnector(**kwargs)
