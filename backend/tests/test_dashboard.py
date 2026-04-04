"""Tests for the dashboard summary endpoints."""

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.main import app
from app.models.agent import Agent
from app.models.audit_log import AuditLog
from app.models.policy import Policy
from app.models.transaction import Transaction

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test and drop them afterwards."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(db):
    def _override():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = _override
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_agent(db, *, name="TestAgent", status="ACTIVE", **kwargs):
    agent = Agent(name=name, status=status, **kwargs)
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def _make_policy(db, *, name="Policy", policy_type="SPEND_LIMIT", is_active=True, parameters=None):
    policy = Policy(
        name=name,
        policy_type=policy_type,
        is_active=is_active,
        parameters=json.dumps(parameters or {}),
    )
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return policy


def _make_transaction(db, agent_id, *, amount=100.0, status="PENDING", created_at=None):
    tx = Transaction(
        agent_id=agent_id,
        recipient="0xRecipient",
        amount=amount,
        status=status,
    )
    if created_at:
        tx.created_at = created_at
    db.add(tx)
    db.commit()
    db.refresh(tx)
    return tx


def _make_audit_log(db, entity_id, *, entity_type="agent", action="TEST"):
    entry = AuditLog(
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


# ---------------------------------------------------------------------------
# GET /api/dashboard/summary
# ---------------------------------------------------------------------------


class TestDashboardSummary:
    def test_empty_database(self, client):
        resp = client.get("/api/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_agents"] == 0
        assert data["active_agents"] == 0
        assert data["total_policies"] == 0
        assert data["total_transactions"] == 0
        assert data["approved_transactions"] == 0
        assert data["denied_transactions"] == 0
        assert data["escalated_transactions"] == 0
        assert data["pending_approvals"] == 0
        assert data["executed_transactions"] == 0
        assert data["total_volume_submitted"] == 0.0
        assert data["total_volume_approved"] == 0.0
        assert data["total_volume_executed"] == 0.0

    def test_with_data(self, client, db):
        agent1 = _make_agent(db, name="Agent1", status="ACTIVE")
        agent2 = _make_agent(db, name="Agent2", status="SUSPENDED")

        _make_policy(db, name="P1")
        _make_policy(db, name="P2", is_active=False)

        _make_transaction(db, agent1.id, amount=50.0, status="APPROVED")
        _make_transaction(db, agent1.id, amount=200.0, status="DENIED")
        _make_transaction(db, agent2.id, amount=300.0, status="ESCALATED")
        _make_transaction(db, agent1.id, amount=100.0, status="PENDING")
        _make_transaction(db, agent1.id, amount=75.0, status="EXECUTED")

        resp = client.get("/api/dashboard/summary")
        assert resp.status_code == 200
        data = resp.json()

        assert data["total_agents"] == 2
        assert data["active_agents"] == 1
        assert data["total_policies"] == 2
        assert data["total_transactions"] == 5
        assert data["approved_transactions"] == 1
        assert data["denied_transactions"] == 1
        assert data["escalated_transactions"] == 1
        assert data["pending_approvals"] == 1
        assert data["executed_transactions"] == 1
        assert data["total_volume_submitted"] == 725.0
        assert data["total_volume_approved"] == 50.0
        assert data["total_volume_executed"] == 75.0


# ---------------------------------------------------------------------------
# GET /api/dashboard/agent/{agent_id}/summary
# ---------------------------------------------------------------------------


class TestAgentDashboardSummary:
    def test_agent_not_found(self, client):
        resp = client.get("/api/dashboard/agent/nonexistent/summary")
        assert resp.status_code == 404

    def test_agent_summary_empty(self, client, db):
        agent = _make_agent(db)
        resp = client.get(f"/api/dashboard/agent/{agent.id}/summary")
        assert resp.status_code == 200
        data = resp.json()

        assert data["agent"]["id"] == agent.id
        assert data["transactions_today"] == 0
        assert data["approved_today"] == 0
        assert data["denied_today"] == 0
        assert data["escalated_today"] == 0
        assert data["spent_today"] == 0.0
        assert data["remaining_daily_budget"] is None
        assert data["recent_transactions"] == []
        assert data["recent_audit_events"] == []

    def test_agent_summary_with_todays_transactions(self, client, db):
        agent = _make_agent(db)
        _make_policy(db, parameters={"limit": 1000.0})

        # Today's transactions
        _make_transaction(db, agent.id, amount=100.0, status="APPROVED")
        _make_transaction(db, agent.id, amount=200.0, status="DENIED")
        _make_transaction(db, agent.id, amount=50.0, status="ESCALATED")
        _make_transaction(db, agent.id, amount=150.0, status="EXECUTED")

        resp = client.get(f"/api/dashboard/agent/{agent.id}/summary")
        assert resp.status_code == 200
        data = resp.json()

        assert data["transactions_today"] == 4
        assert data["approved_today"] == 1
        assert data["denied_today"] == 1
        assert data["escalated_today"] == 1
        # spent_today = APPROVED (100) + EXECUTED (150)
        assert data["spent_today"] == 250.0
        # remaining = 1000 - 250
        assert data["remaining_daily_budget"] == 750.0

    def test_agent_summary_recent_transactions(self, client, db):
        agent = _make_agent(db)

        for i in range(15):
            _make_transaction(db, agent.id, amount=float(i + 1), status="APPROVED")

        resp = client.get(f"/api/dashboard/agent/{agent.id}/summary")
        data = resp.json()

        # Should return at most 10 recent transactions
        assert len(data["recent_transactions"]) == 10

    def test_agent_summary_recent_audit_events(self, client, db):
        agent = _make_agent(db)

        for _ in range(15):
            _make_audit_log(db, agent.id)

        resp = client.get(f"/api/dashboard/agent/{agent.id}/summary")
        data = resp.json()

        # Should return at most 10 recent audit events
        assert len(data["recent_audit_events"]) == 10

    def test_agent_summary_active_policies(self, client, db):
        agent = _make_agent(db)
        _make_policy(db, name="Active1")
        _make_policy(db, name="Active2")
        _make_policy(db, name="Inactive", is_active=False)

        resp = client.get(f"/api/dashboard/agent/{agent.id}/summary")
        data = resp.json()

        assert len(data["active_policies"]) == 2

    def test_remaining_budget_no_spend_policy(self, client, db):
        agent = _make_agent(db)
        _make_policy(db, name="Allowlist", policy_type="ALLOWLIST")

        _make_transaction(db, agent.id, amount=100.0, status="APPROVED")

        resp = client.get(f"/api/dashboard/agent/{agent.id}/summary")
        data = resp.json()

        assert data["remaining_daily_budget"] is None
