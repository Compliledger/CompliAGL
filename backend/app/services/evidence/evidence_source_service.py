"""EvidenceSource registry persistence.

Registers the connectors available to a tenant as persistent, inspectable
:class:`~app.models.evidence_source.EvidenceSource` records. This keeps the
authoritative-source registry queryable (which connectors exist, what they can
serve, whether they are mock) without exposing any secrets — only an indirect
``auth_config_reference`` is stored.
"""

from __future__ import annotations

import json
from typing import Sequence

from sqlalchemy.orm import Session

from app.models.evidence_source import EvidenceSource
from app.repositories.canonical import EvidenceSourceRepository
from app.services.evidence.connectors import ConnectorRegistry


def sync_registry(
    db: Session, organization_id: str, registry: ConnectorRegistry
) -> list[EvidenceSource]:
    """Idempotently persist each connector in *registry* as an EvidenceSource."""
    repo = EvidenceSourceRepository(db)
    out: list[EvidenceSource] = []
    for connector in registry.all():
        existing = repo.get_by_connector_id(
            organization_id, connector.connector_id
        )
        desc = connector.describe()
        if existing is None:
            obj = EvidenceSource(
                organization_id=organization_id,
                connector_id=connector.connector_id,
                source_type=connector.source_type,
                supported_evidence_types=json.dumps(
                    desc["supported_evidence_types"]
                ),
                auth_config_reference=connector.auth_config_reference,
                is_mock=bool(connector.is_mock),
                trusted_issuers=json.dumps(desc["trusted_issuers"]),
                timeout_seconds=str(connector.timeout_seconds),
                retry_policy=json.dumps(desc["retry_policy"]),
                status="ACTIVE",
            )
            out.append(repo.add(obj))
        else:
            existing.source_type = connector.source_type
            existing.supported_evidence_types = json.dumps(
                desc["supported_evidence_types"]
            )
            existing.auth_config_reference = connector.auth_config_reference
            existing.is_mock = bool(connector.is_mock)
            existing.trusted_issuers = json.dumps(desc["trusted_issuers"])
            existing.timeout_seconds = str(connector.timeout_seconds)
            existing.retry_policy = json.dumps(desc["retry_policy"])
            out.append(repo.save(existing))
    return out


def list_(
    db: Session, organization_id: str, *, skip: int = 0, limit: int = 100
) -> Sequence[EvidenceSource]:
    return EvidenceSourceRepository(db).list(
        organization_id, skip=skip, limit=limit
    )


def get(db: Session, organization_id: str, resource_id: str):
    return EvidenceSourceRepository(db).get(organization_id, resource_id)
