"""Serialization and schema-version tests."""

from __future__ import annotations

from app.models._mixins import CANONICAL_SCHEMA_VERSION
from app.schemas.canonical.intent import IntentResponse
from app.schemas.canonical.operational_context import OperationalContextResponse
from app.schemas.canonical.serialization import orm_to_dict
from app.services.canonical import (
    intent_service,
    operational_context_service,
)
from tests.canonical_factories import context_payload, intent_payload


def test_orm_to_dict_parses_json_text_fields(db_session):
    intent = intent_service.create(
        db_session, intent_payload(parameters={"route": "SFO-JFK"})
    )
    data = orm_to_dict(intent)
    # JSON-text column becomes a native dict.
    assert data["parameters"] == {"route": "SFO-JFK"}
    assert data["schema_version"] == CANONICAL_SCHEMA_VERSION


def test_response_schema_round_trips_from_orm(db_session):
    intent = intent_service.create(db_session, intent_payload())
    response = IntentResponse.model_validate(orm_to_dict(intent))
    assert response.id == intent.id
    assert response.schema_version == CANONICAL_SCHEMA_VERSION
    assert response.amount_minor == intent.amount_minor
    # Re-serialise to JSON and confirm the parsed parameters survive.
    dumped = response.model_dump()
    assert dumped["parameters"] == {"route": "SFO-JFK"}


def test_operational_context_state_snapshots_serialize(db_session):
    ctx = operational_context_service.create(
        db_session,
        context_payload(
            allowance_state={"remaining_minor": 500000, "currency": "USD"},
        ),
    )
    response = OperationalContextResponse.model_validate(orm_to_dict(ctx))
    # Monetary value inside a state snapshot is an integer (minor units).
    assert response.allowance_state == {"remaining_minor": 500000, "currency": "USD"}
    assert isinstance(response.allowance_state["remaining_minor"], int)
    assert response.context_hash is not None


def test_schema_version_defaults_are_persisted(db_session):
    intent = intent_service.create(db_session, intent_payload())
    assert intent.schema_version == CANONICAL_SCHEMA_VERSION
    # The intent's own semantic version is distinct from storage schema_version.
    assert intent.version == "1"
