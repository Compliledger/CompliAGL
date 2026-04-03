"""Database initialisation and seed utility for local hackathon development.

Creates all tables defined in ``app.models`` and optionally seeds demo
agents, policies, transactions, and audit-log entries so a developer can
start exploring CompliAGL immediately.

Usage
-----
::

    python -m app.db.init_db          # create tables + seed
    python -m app.db.init_db --no-seed  # create tables only
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

# Models & Base -----------------------------------------------------------
from app.models.models import (
    Agent,
    AuditLog,
    Base,
    Decision,
    Policy,
    ProofRecord,
    Transaction,
)
from app.utils.enums import (
    ActorType,
    DecisionResult,
    PolicyStatus,
    ProofStatus,
    RiskLevel,
    TransactionStatus,
)

# ---- configuration ------------------------------------------------------

DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./compliagl.db")

# ---- helpers -------------------------------------------------------------


def _uid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---- table creation ------------------------------------------------------


def create_tables(database_url: str = DATABASE_URL) -> None:
    """Create every table registered on :pydata:`Base.metadata`."""
    connect_args: dict = {}
    if "sqlite" in database_url:
        connect_args["check_same_thread"] = False

    engine = create_engine(database_url, connect_args=connect_args)
    Base.metadata.create_all(bind=engine)
    print(f"[init_db] Tables created ({database_url})")


# ---- seed data -----------------------------------------------------------


def seed(database_url: str = DATABASE_URL) -> None:
    """Insert demo agents, policies, transactions, and audit-log entries.

    The function is **idempotent** — it checks for an existing agent
    wallet address before inserting so re-running is safe.
    """
    connect_args: dict = {}
    if "sqlite" in database_url:
        connect_args["check_same_thread"] = False

    engine = create_engine(database_url, connect_args=connect_args)

    # Ensure tables exist before seeding
    if not inspect(engine).has_table("agents"):
        Base.metadata.create_all(bind=engine)

    with Session(engine) as session:
        # --- guard: skip if data already present ---
        existing = (
            session.query(Agent)
            .filter_by(wallet_address="agent_wallet_travel_001")
            .first()
        )
        if existing is not None:
            print("[init_db] Seed data already present — skipping.")
            return

        now = _now()

        # ---- Agents ---------------------------------------------------------

        travel_agent = Agent(
            id=_uid(),
            name="TravelAgent-01",
            actor_type=ActorType.AGENT.value,
            wallet_address="agent_wallet_travel_001",
            created_at=now,
            updated_at=now,
        )

        research_agent = Agent(
            id=_uid(),
            name="ResearchAgent-01",
            actor_type=ActorType.AGENT.value,
            wallet_address="agent_wallet_research_001",
            created_at=now,
            updated_at=now,
        )

        session.add_all([travel_agent, research_agent])
        session.flush()  # populate PKs for FK references

        # ---- Policies -------------------------------------------------------

        travel_policy = Policy(
            id=_uid(),
            agent_id=travel_agent.id,
            name="TravelAgent-01 spend policy",
            description=(
                "daily_budget=500, per_tx_limit=450, "
                "escalation_threshold=250"
            ),
            status=PolicyStatus.ACTIVE.value,
            max_spend_per_tx=450.0,
            allowed_assets=json.dumps(
                ["airline_api", "hotel_api", "restaurant_api"]
            ),
            allowed_recipients=json.dumps(
                ["xrpl", "base", "ethereum"]
            ),
            risk_level=RiskLevel.LOW.value,
            created_at=now,
            updated_at=now,
        )

        research_policy = Policy(
            id=_uid(),
            agent_id=research_agent.id,
            name="ResearchAgent-01 spend policy",
            description=(
                "daily_budget=100, per_tx_limit=50, "
                "escalation_threshold=40"
            ),
            status=PolicyStatus.ACTIVE.value,
            max_spend_per_tx=50.0,
            allowed_assets=json.dumps(
                ["firecrawl", "news_api", "research_api"]
            ),
            allowed_recipients=json.dumps(["base", "ethereum"]),
            risk_level=RiskLevel.LOW.value,
            created_at=now,
            updated_at=now,
        )

        session.add_all([travel_policy, research_policy])
        session.flush()

        # ---- Transactions ---------------------------------------------------

        tx1 = Transaction(
            id=_uid(),
            agent_id=travel_agent.id,
            amount=120.00,
            asset="USD",
            recipient="hotel_api",
            status=TransactionStatus.APPROVED.value,
            created_at=now,
            updated_at=now,
        )

        tx2 = Transaction(
            id=_uid(),
            agent_id=travel_agent.id,
            amount=475.00,
            asset="USD",
            recipient="airline_api",
            status=TransactionStatus.DENIED.value,
            created_at=now,
            updated_at=now,
        )

        tx3 = Transaction(
            id=_uid(),
            agent_id=research_agent.id,
            amount=35.00,
            asset="USD",
            recipient="firecrawl",
            status=TransactionStatus.APPROVED.value,
            created_at=now,
            updated_at=now,
        )

        tx4 = Transaction(
            id=_uid(),
            agent_id=research_agent.id,
            amount=45.00,
            asset="USD",
            recipient="news_api",
            status=TransactionStatus.ESCALATED.value,
            created_at=now,
            updated_at=now,
        )

        session.add_all([tx1, tx2, tx3, tx4])
        session.flush()

        # ---- Decisions ------------------------------------------------------

        dec1 = Decision(
            id=_uid(),
            transaction_id=tx1.id,
            result=DecisionResult.APPROVED.value,
            reason="Amount $120 within per-tx limit of $450.",
            rules_evaluated=3,
            rules_passed=3,
            rules_failed=0,
            created_at=now,
        )

        dec2 = Decision(
            id=_uid(),
            transaction_id=tx2.id,
            result=DecisionResult.DENIED.value,
            reason="Amount $475 exceeds per-tx limit of $450.",
            rules_evaluated=3,
            rules_passed=2,
            rules_failed=1,
            created_at=now,
        )

        dec3 = Decision(
            id=_uid(),
            transaction_id=tx3.id,
            result=DecisionResult.APPROVED.value,
            reason="Amount $35 within per-tx limit of $50.",
            rules_evaluated=3,
            rules_passed=3,
            rules_failed=0,
            created_at=now,
        )

        dec4 = Decision(
            id=_uid(),
            transaction_id=tx4.id,
            result=DecisionResult.ESCALATED.value,
            reason="Amount $45 exceeds escalation threshold of $40.",
            rules_evaluated=3,
            rules_passed=2,
            rules_failed=1,
            created_at=now,
        )

        session.add_all([dec1, dec2, dec3, dec4])
        session.flush()

        # ---- Proof records --------------------------------------------------

        proof1 = ProofRecord(
            id=_uid(),
            decision_id=dec1.id,
            verdict=DecisionResult.APPROVED.value,
            policy_snapshot=json.dumps(
                {"policy": travel_policy.name, "max_spend_per_tx": 450}
            ),
            signature="sha256:demo_sig_travel_approved",
            status=ProofStatus.GENERATED.value,
            created_at=now,
        )

        proof2 = ProofRecord(
            id=_uid(),
            decision_id=dec2.id,
            verdict=DecisionResult.DENIED.value,
            policy_snapshot=json.dumps(
                {"policy": travel_policy.name, "max_spend_per_tx": 450}
            ),
            signature="sha256:demo_sig_travel_denied",
            status=ProofStatus.GENERATED.value,
            created_at=now,
        )

        session.add_all([proof1, proof2])

        # ---- Audit-log entries ----------------------------------------------

        logs = [
            AuditLog(
                id=_uid(),
                event_type="TRANSACTION_APPROVED",
                actor_type=ActorType.AGENT.value,
                actor_id=travel_agent.id,
                resource_type="transaction",
                resource_id=tx1.id,
                detail="Hotel booking $120 approved by policy engine.",
                created_at=now,
            ),
            AuditLog(
                id=_uid(),
                event_type="TRANSACTION_DENIED",
                actor_type=ActorType.AGENT.value,
                actor_id=travel_agent.id,
                resource_type="transaction",
                resource_id=tx2.id,
                detail="Airline ticket $475 denied — exceeds per-tx limit.",
                created_at=now,
            ),
            AuditLog(
                id=_uid(),
                event_type="TRANSACTION_APPROVED",
                actor_type=ActorType.AGENT.value,
                actor_id=research_agent.id,
                resource_type="transaction",
                resource_id=tx3.id,
                detail="Firecrawl query $35 approved by policy engine.",
                created_at=now,
            ),
            AuditLog(
                id=_uid(),
                event_type="TRANSACTION_ESCALATED",
                actor_type=ActorType.AGENT.value,
                actor_id=research_agent.id,
                resource_type="transaction",
                resource_id=tx4.id,
                detail="News API $45 escalated — above escalation threshold.",
                created_at=now,
            ),
        ]

        session.add_all(logs)

        session.commit()
        print("[init_db] Seed data inserted successfully.")


# ---- CLI entry point -----------------------------------------------------


def main() -> None:
    """CLI entry point invoked via ``python -m app.db.init_db``."""
    parser = argparse.ArgumentParser(
        description="Initialise the CompliAGL database and optionally seed demo data.",
    )
    parser.add_argument(
        "--no-seed",
        action="store_true",
        default=False,
        help="Create tables without inserting demo seed data.",
    )
    parser.add_argument(
        "--db-url",
        type=str,
        default=DATABASE_URL,
        help=f"SQLAlchemy database URL (default: {DATABASE_URL}).",
    )

    args = parser.parse_args()

    create_tables(database_url=args.db_url)

    if not args.no_seed:
        seed(database_url=args.db_url)

    print("[init_db] Done.")


if __name__ == "__main__":
    main()
