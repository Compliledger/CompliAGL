"""Hedera Agent Kit demo governance package content.

Authors the executable governance package that backs the public
demo.compliagl.compliledger.com Hedera demo (Normal Action / Oracle Anomaly
Incident / Human Approval Required scenarios), and the local
CompliAGL-Hedera-Agent-Kit-Adapter e2e demo (examples/e2e-real-services-demo.ts).

This package is idempotently created/validated/approved/published on every
boot via seed_hedera_demo_package() in app/db/seed.py -- the same pattern
already used for the HarborStone package. This backend's persistence is
non-durable SQLite (recreated on every deploy/restart per this module's own
seeding pattern), so without this the governance package silently
disappears on every restart and both demos start returning DENY with
reason code NO_APPLICABLE_POLICY until someone notices and manually
republishes it.

Field names and expression syntax are confirmed directly from the Adapter's
source (CompliAGL-Hedera-Agent-Kit-Adapter/src/hedera-action-mapper.ts): the
Adapter's `facts` bag is forwarded verbatim into CompliAGL's
OperationalContext.operational_state_snapshot, which is what
decision_conditions evaluate against. Verified live against production on
2026-09-07 -- all three scenarios return the expected outcome.
"""

from __future__ import annotations

from app.schemas.canonical.governance_package import (
    ExecutableGovernancePackageCreate,
)

PACKAGE_NAME = "hedera-demo-governance"
PACKAGE_VERSION = "1.0.1"

REQ_ORACLE_CORROBORATION = "REQ-ORACLE-CORROBORATION"
REQ_EXPOSURE_LIMIT = "REQ-EXPOSURE-LIMIT"
REQ_AUTONOMOUS_TRANSFER_LIMIT = "REQ-AUTONOMOUS-TRANSFER-LIMIT"

# Exposure limit for anomalous DeFi borrow actions (Bonzo-style oracle
# incident scenario). USD, not minor units -- matches the Adapter's
# requested_borrow_usd fact, which is a plain float, not integer cents.
EXPOSURE_LIMIT_USD = 1_000_000

# Autonomous transfer threshold above which a human must approve
# (Human Approval Required scenario). HBAR, matches the Adapter's
# requested_transfer_amount_hbar fact.
AUTONOMOUS_TRANSFER_LIMIT_HBAR = 1_000


def build_hedera_demo_package(
    organization_id: str,
) -> ExecutableGovernancePackageCreate:
    """Return the (not-yet-published) Hedera demo package create payload.

    Caller is responsible for running it through the real lifecycle
    (governance_package_service.create -> validate -> approve -> publish)
    -- this function only builds the content. See seed_hedera_demo_package
    in app/db/seed.py for the idempotent boot-time caller.
    """
    return ExecutableGovernancePackageCreate(
        organization_id=organization_id,
        package_name=PACKAGE_NAME,
        package_version=PACKAGE_VERSION,
        content_schema_version="1.0.0",
        requirements=[
            {
                "requirement_id": REQ_ORACLE_CORROBORATION,
                "source_reference": "Hedera Agent Kit demo - Bonzo oracle incident",
                "normalized_text": (
                    "DeFi borrow actions must have oracle-corroborated pricing."
                ),
                "requirement_type": "FINANCIAL",
                "classification": "PROHIBITION",
                "applicability_expression": "intent.action == 'DEFI_BORROW'",
                "applicability_criteria": {
                    "op": "equals",
                    "field": "intent.action",
                    "value": "DEFI_BORROW",
                },
                "severity": "CRITICAL",
            },
            {
                "requirement_id": REQ_EXPOSURE_LIMIT,
                "source_reference": "Hedera Agent Kit demo - exposure limits",
                "normalized_text": (
                    f"DeFi borrow actions must not exceed "
                    f"${EXPOSURE_LIMIT_USD:,} USD exposure."
                ),
                "requirement_type": "FINANCIAL",
                "classification": "PROHIBITION",
                "applicability_expression": "intent.action == 'DEFI_BORROW'",
                "applicability_criteria": {
                    "op": "equals",
                    "field": "intent.action",
                    "value": "DEFI_BORROW",
                },
                "severity": "CRITICAL",
            },
            {
                "requirement_id": REQ_AUTONOMOUS_TRANSFER_LIMIT,
                "source_reference": (
                    "Hedera Agent Kit demo - autonomous authority limits"
                ),
                "normalized_text": (
                    f"Autonomous HBAR transfers above "
                    f"{AUTONOMOUS_TRANSFER_LIMIT_HBAR} HBAR require human "
                    f"approval."
                ),
                "requirement_type": "FINANCIAL",
                "classification": "PROHIBITION",
                "applicability_expression": "intent.action == 'TRANSFER'",
                "applicability_criteria": {
                    "op": "equals",
                    "field": "intent.action",
                    "value": "TRANSFER",
                },
                "severity": "HIGH",
            },
        ],
        control_definitions=[],
        decision_conditions=[
            {
                "condition_id": "oracle-anomaly-deny",
                "expression": (
                    "intent.action == 'DEFI_BORROW' and "
                    "context.operational_state_snapshot.oracle_corroborated == False"
                ),
                "resulting_decision": "DENIED",
                "priority": 10,
                "reason_code": "ORACLE_PRICE_ANOMALY",
                "terminal": True,
            },
            {
                "condition_id": "exposure-limit-deny",
                "expression": (
                    "intent.action == 'DEFI_BORROW' and "
                    "context.operational_state_snapshot.requested_borrow_usd > "
                    f"{EXPOSURE_LIMIT_USD}"
                ),
                "resulting_decision": "DENIED",
                "priority": 20,
                "reason_code": "EXPOSURE_LIMIT_EXCEEDED",
                "terminal": True,
            },
            {
                "condition_id": "transfer-escalation",
                "expression": (
                    "intent.action == 'TRANSFER' and "
                    "context.operational_state_snapshot.requested_transfer_amount_hbar > "
                    f"{AUTONOMOUS_TRANSFER_LIMIT_HBAR}"
                ),
                "resulting_decision": "ESCALATED",
                "priority": 30,
                "reason_code": "EXCEEDS_AUTONOMOUS_AUTHORITY",
                "terminal": True,
            },
            {
                "condition_id": "default-approve",
                "expression": "True",
                "resulting_decision": "APPROVED",
                "priority": 1000,
                "reason_code": "POLICY_OK",
                "terminal": True,
            },
        ],
        evidence_requirements=[],
        applicability_rules=[
            {"intent_action": "TRANSFER", "intent_type": "WORKFLOW_ACTION"},
            {"intent_action": "DEFI_BORROW", "intent_type": "WORKFLOW_ACTION"},
        ],
        metadata={
            "demo": "hedera-agent-kit",
            "purpose": (
                "Backs demo.compliagl.compliledger.com and the local "
                "CompliAGL-Hedera-Agent-Kit-Adapter e2e demo."
            ),
        },
    )
