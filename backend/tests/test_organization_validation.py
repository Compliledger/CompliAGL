"""Organization existence is a real, enforced constraint.

Deliberately does **not** use the ``db_session``/``api_client`` fixtures from
``conftest.py`` — those monkeypatch ``organization_service.exists_active`` to
auto-register any org a test writes under, which is exactly the behavior
these tests need to prove does *not* happen for real callers.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import Base, get_db
from app.db import init_db  # noqa: F401
from app.main import app
from app.models.organization import Organization
from app.models.target import Target
from app.repositories.canonical import TargetRepository
from app.schemas.canonical.target import TargetCreate
from app.services.canonical import organization_service, target_service
from app.services.canonical.errors import OrganizationNotFoundError
from app.utils.canonical_enums import TargetType

UNKNOWN_ORG = "org-that-was-never-registered"
REAL_ORG = "org-really-registered"


def _make_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return Session(), engine


def test_exists_active_false_for_unknown_org():
    db, engine = _make_session()
    try:
        assert organization_service.exists_active(db, UNKNOWN_ORG) is False
    finally:
        db.close()
        engine.dispose()


def test_exists_active_true_for_registered_active_org():
    db, engine = _make_session()
    try:
        db.add(
            Organization(
                organization_id=REAL_ORG,
                organization_name="Really Registered",
                status="ACTIVE",
            )
        )
        db.commit()
        assert organization_service.exists_active(db, REAL_ORG) is True
    finally:
        db.close()
        engine.dispose()


def test_exists_active_false_for_inactive_org():
    db, engine = _make_session()
    try:
        db.add(
            Organization(
                organization_id=REAL_ORG,
                organization_name="Really Registered",
                status="SUSPENDED",
            )
        )
        db.commit()
        assert organization_service.exists_active(db, REAL_ORG) is False
    finally:
        db.close()
        engine.dispose()


def test_repository_write_rejects_unknown_org():
    db, engine = _make_session()
    try:
        obj = Target(
            organization_id=UNKNOWN_ORG,
            target_type=TargetType.MERCHANT.value,
            external_identifier="merchant-1",
        )
        with pytest.raises(OrganizationNotFoundError):
            TargetRepository(db).add(obj)
    finally:
        db.close()
        engine.dispose()


def test_repository_read_rejects_unknown_org():
    db, engine = _make_session()
    try:
        with pytest.raises(OrganizationNotFoundError):
            target_service.list_(db, UNKNOWN_ORG)
    finally:
        db.close()
        engine.dispose()


def test_service_create_rejects_unknown_org():
    db, engine = _make_session()
    try:
        payload = TargetCreate(
            organization_id=UNKNOWN_ORG,
            target_type=TargetType.MERCHANT,
            external_identifier="merchant-1",
        )
        with pytest.raises(OrganizationNotFoundError):
            target_service.create(db, payload)
    finally:
        db.close()
        engine.dispose()


def test_api_rejects_unknown_org_header():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
        client = TestClient(app)
        resp = client.get(
            "/api/v1/targets", headers={"X-Organization-Id": UNKNOWN_ORG}
        )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_api_rejects_unknown_org_in_body():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
        client = TestClient(app)
        resp = client.post(
            "/api/v1/targets",
            json={
                "organization_id": UNKNOWN_ORG,
                "target_type": "MERCHANT",
                "external_identifier": "merchant-1",
            },
        )
        assert resp.status_code == 404
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
