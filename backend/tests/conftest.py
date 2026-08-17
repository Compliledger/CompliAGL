"""Shared pytest fixtures for the canonical runtime test suite."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

# Importing app.db.init_db / app.main registers every ORM model on Base.metadata.
from app.core.database import Base, get_db
from app.db import init_db  # noqa: F401
from app.main import app
from app.models.organization import Organization
from app.services.canonical import organization_service


def _make_engine():
    return create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _autoregistering_exists_active(db: Session, organization_id: str) -> bool:
    """Test-only replacement for ``organization_service.exists_active``.

    Tests across this suite freely invent ``organization_id`` strings
    (``org-alpha``, ``org-travel``, ...) with no separate registration step.
    Organization existence is now a real, enforced check (see
    ``app.services.canonical.organization_service``), so — scoped to the
    test engine only, via monkeypatch, never touching production code — this
    registers an org the first time it's referenced, the same way
    ``organization_id`` used to be accepted implicitly everywhere. Tests that
    specifically want to prove *rejection* of an unknown org
    (``tests/test_organization_validation.py``) call the real
    ``organization_service.exists_active`` directly instead of going through
    this fixture-patched path.
    """
    org = db.get(Organization, organization_id)
    if org is None:
        db.add(
            Organization(
                organization_id=organization_id,
                organization_name=organization_id,
                status="ACTIVE",
            )
        )
        db.flush()
        return True
    return org.status == "ACTIVE"


@pytest.fixture(autouse=True)
def _autoregister_organizations(request, monkeypatch):
    """Auto-register any org a test writes under, for every test but our own.

    ``tests/test_organization_validation.py`` exists specifically to prove
    real rejection of unregistered orgs, so it must see the genuine
    ``organization_service.exists_active`` — every other test in the suite
    gets the auto-registering version, regardless of which local fixture
    (shared or per-file) builds its session, since this is autouse.
    """
    if request.module.__name__ != "tests.test_organization_validation":
        monkeypatch.setattr(
            organization_service, "exists_active", _autoregistering_exists_active
        )


@pytest.fixture()
def db_session():
    """Yield a fresh in-memory database session with all tables created."""
    engine = _make_engine()
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = Session()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def api_client():
    """Yield a TestClient wired to an isolated in-memory database."""
    engine = _make_engine()
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def _override_get_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
