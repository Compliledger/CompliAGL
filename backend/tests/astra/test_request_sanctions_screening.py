"""request_sanctions_screening delegates to the real SENTRY connector and
persists the result as RawEvidence."""

from __future__ import annotations

import json

import pytest

from app.astra.context import build_context
from app.astra.tools.dispatch import execute_tool_call
from app.db import seed
from app.repositories.canonical import RawEvidenceRepository

ORG = "harborstone-demo"
CASE = "HARBORSTONE-2024-0042"


@pytest.fixture()
def ctx(db_session):
    seed.seed_organizations(db_session)
    seed.seed_harborstone_actors(db_session)
    return build_context(
        db=db_session, organization_id=ORG, persona_name="AIRA", case_id=CASE,
        correlation_id="astra-test-corr",
    )


def test_clean_subject_returns_no_match(ctx):
    out = execute_tool_call(
        ctx,
        "request_sanctions_screening",
        {"subject_id": "wallet_001", "subject_type": "wallet", "reason": "pre-flight"},
    )
    assert out["result"] == "NO_MATCH"
    assert out["requires_human_review"] is False
    assert out["simulation"] is True
    assert out["screened_by"] == "agent:harborstone:sentry"
    assert out["delegated_by"] == "agent:harborstone:aira"
    assert out["raw_evidence_id"]


def test_potential_match_flags_human_review(ctx):
    out = execute_tool_call(
        ctx,
        "request_sanctions_screening",
        {"subject_id": "wallet_002", "subject_type": "wallet", "reason": None},
    )
    assert out["result"] == "POTENTIAL_MATCH"
    assert out["requires_human_review"] is True
    assert out["risk_level"] == "HIGH"


def test_result_is_persisted_as_raw_evidence_with_delegation_provenance(ctx):
    out = execute_tool_call(
        ctx,
        "request_sanctions_screening",
        {"subject_id": "wallet_003", "subject_type": "wallet", "reason": "escalation check"},
    )
    raw = RawEvidenceRepository(ctx.db).get(ORG, out["raw_evidence_id"])
    assert raw is not None
    assert raw.collection_job_id == "astra-delegated-screening:astra-test-corr"
    assert raw.evidence_requirement_id == "EV-HARBORSTONE-SANCTIONS-SCREENING"
    assert raw.subject_id == "wallet_003"
    provenance = json.loads(raw.provenance)
    assert provenance["collected_via"] == "astra_tool_delegation"
    assert provenance["delegation"]["requesting_agent_id"] == "agent:harborstone:aira"
    assert provenance["delegation"]["reason"] == "escalation check"
    claims = json.loads(raw.claims)
    assert claims["integrity_hash"] == out["integrity_hash"]


def test_empty_subject_is_rejected(ctx):
    from app.astra.errors import ToolValidationError

    with pytest.raises(ToolValidationError):
        execute_tool_call(
            ctx,
            "request_sanctions_screening",
            {"subject_id": "  ", "subject_type": "wallet", "reason": None},
        )
