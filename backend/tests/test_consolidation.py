"""Consolidation tests for the canonical persistent runtime.

These tests assert the Phase-1 acceptance criteria:

* one persistent actor implementation,
* one persistent policy implementation,
* one canonical decision engine (APPROVED / DENIED / ESCALATED),
* one canonical persistent AIProof,
* runtime state survives an application "restart",
* x402 is an *optional* execution adapter (not the runtime),
* execution never substitutes zero amounts or a default currency.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# importing init_db registers every ORM model (incl. AIProof) on Base.metadata
from app.db import init_db  # noqa: F401
from app.core.database import Base
from app.db.seed import (
    DEMO_TRAVEL_AGENT_ID,
    DEMO_TRAVEL_POLICY_ID,
    seed_demo_data,
)
from app.mvp2.proof.aiproof import build_aiproof
from app.mvp2.schemas.decision import DecisionResult
from app.services import (
    actor_registry,
    aiproof_service,
    decision_engine,
    policy_repository,
)


def _make_sessionmaker(db_path: str):
    engine = create_engine(
        f"sqlite:///{db_path}", connect_args={"check_same_thread": False}
    )
    Base.metadata.create_all(bind=engine)
    return engine, sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---------------------------------------------------------------------------
# Persistence survives restart
# ---------------------------------------------------------------------------


def test_actor_policy_and_proof_survive_restart(tmp_path):
    db_file = str(tmp_path / "runtime.db")

    # --- First "process": seed + store a proof, then dispose the engine. ---
    engine1, Session1 = _make_sessionmaker(db_file)
    db1 = Session1()
    seed_demo_data(db1)
    bundle = build_aiproof(
        actor_id=str(DEMO_TRAVEL_AGENT_ID),
        intent_id="11111111-1111-1111-1111-111111111111",
        decision="APPROVED",
        decision_reason=["APPROVED_BY_POLICY"],
        execution_adapter="x402",
        execution_status="CONFIRMED",
    )
    stored = aiproof_service.store_proof(db1, bundle)
    proof_hash = stored["proof_hash"]
    db1.close()
    engine1.dispose()

    # --- Second "process": brand-new engine/session on the same file. ---
    engine2, Session2 = _make_sessionmaker(db_file)
    db2 = Session2()

    actor = actor_registry.get_actor(db2, DEMO_TRAVEL_AGENT_ID)
    assert actor is not None and actor.name == "TravelAgent-01"

    policies = policy_repository.list_active_policies(db2)
    assert any(str(p.id) == str(DEMO_TRAVEL_POLICY_ID) for p in policies)

    reloaded = aiproof_service.get_by_hash(db2, proof_hash)
    assert reloaded is not None
    assert reloaded["proof_hash"] == proof_hash
    assert reloaded["decision"] == "APPROVED"
    db2.close()
    engine2.dispose()


# ---------------------------------------------------------------------------
# One canonical decision engine — canonical outcomes
# ---------------------------------------------------------------------------


@pytest.fixture()
def seeded_session(tmp_path):
    engine, Session = _make_sessionmaker(str(tmp_path / "engine.db"))
    db = Session()
    seed_demo_data(db)
    yield db
    db.close()
    engine.dispose()


@pytest.mark.parametrize(
    "amount,currency,expected",
    [
        (100.0, "USDC", DecisionResult.APPROVED),
        (300.0, "USDC", DecisionResult.ESCALATED),
        (600.0, "USDC", DecisionResult.DENIED),
        (100.0, "BTC", DecisionResult.DENIED),
    ],
)
def test_decision_engine_canonical_outcomes(seeded_session, amount, currency, expected):
    result = decision_engine.evaluate_intent(
        seeded_session,
        actor_id=DEMO_TRAVEL_AGENT_ID,
        action="book_flight",
        amount=amount,
        currency=currency,
    )
    assert result.result == expected


# ---------------------------------------------------------------------------
# x402 is an optional adapter, not the runtime
# ---------------------------------------------------------------------------


def test_execution_service_imports_without_x402_being_the_runtime():
    from app.mvp2.execution import service

    adapters = service.available_adapters()
    # The always-available adapters exist independently of x402.
    assert "mock" in adapters
    assert "solana" in adapters
    # mock adapter resolves without touching x402 at all.
    assert service.get_adapter("mock") is not None


# ---------------------------------------------------------------------------
# Execution never substitutes zero amount / default currency
# ---------------------------------------------------------------------------


def test_execution_passes_real_amount_and_currency():
    from app.mvp2.execution import service
    from app.mvp2.execution.adapters.base import BaseExecutionAdapter
    from app.mvp2.schemas.execution import ExecutionRequest
    from uuid import uuid4

    seen: dict = {}

    class RecordingAdapter(BaseExecutionAdapter):
        name = "recording"

        async def execute(self, transaction_id, amount, currency, metadata=None):
            seen["amount"] = amount
            seen["currency"] = currency
            return {"tx_hash": "rec-1", "status": "CONFIRMED"}

        async def get_status(self, tx_hash):
            return "CONFIRMED"

    service._ADAPTER_REGISTRY["recording"] = RecordingAdapter
    try:
        request = ExecutionRequest(
            transaction_id=uuid4(),
            amount=42.5,
            currency="EUR",
            adapter="recording",
        )
        response = asyncio.run(service.execute_authorized_action(request))
    finally:
        service._ADAPTER_REGISTRY.pop("recording", None)

    # The real values are passed through — no zero-amount / USD substitution.
    assert seen == {"amount": 42.5, "currency": "EUR"}
    assert response.tx_hash == "rec-1"
