"""Tests for the HarborStone Demo #3 governance-package seed.

``seed_harborstone_package`` publishes ``build_harborstone_package()``
through the real create -> validate -> approve -> publish lifecycle, scoped
to the ``harborstone-demo`` org, and is idempotent on re-run.

These tests exercise the *seed wiring* only. Package v1.2.1 carries a real
sanctions-screening requirement/control keyed to SENTRY's structured
evidence -- see ``docs/harborstone-sanctions-screening.md`` and
``tests/test_harborstone_package.py``.
"""

from __future__ import annotations

from app.db.harborstone_package import PACKAGE_NAME, PACKAGE_VERSION
from app.db.seed import (
    HARBORSTONE_ORG_ID,
    seed_harborstone_package,
    seed_organizations,
)
from app.services.canonical import governance_package_service
from app.utils.canonical_enums import PackageStatus


def test_seed_publishes_the_package(db_session):
    seed_organizations(db_session)
    seed_harborstone_package(db_session)

    published = governance_package_service.get_published_version(
        db_session, HARBORSTONE_ORG_ID, PACKAGE_NAME, PACKAGE_VERSION
    )
    assert published is not None
    assert published.status == PackageStatus.PUBLISHED.value
    assert published.requires_authority_context is True
    assert published.approved_by == "seed-bootstrap"
    assert published.approval_rationale
    # Authority check disabled by default -> no verified authority snapshot.
    assert published.approver_authority_hash is None


def test_seed_is_idempotent(db_session):
    seed_organizations(db_session)
    seed_harborstone_package(db_session)
    seed_harborstone_package(db_session)
    seed_harborstone_package(db_session)

    packages = governance_package_service.list_(
        db_session, HARBORSTONE_ORG_ID, package_name=PACKAGE_NAME
    )
    assert len(list(packages)) == 1


def test_published_package_has_the_corrected_decision_conditions(db_session):
    """Guards that the seed publishes the vocabulary-corrected package, not a
    stale build (credential_expired out, resource_scope_unmatched in)."""
    seed_organizations(db_session)
    seed_harborstone_package(db_session)
    published = governance_package_service.get_published_version(
        db_session, HARBORSTONE_ORG_ID, PACKAGE_NAME, PACKAGE_VERSION
    )
    document = governance_package_service.build_package_document(published)
    denied = next(
        c
        for c in document["decision_conditions"]
        if c["condition_id"] == "DC-HARBORSTONE-AUTHORITY-DENIED"
    )
    assert "resource_scope_unmatched" in denied["expression"]
    assert "credential_expired" not in denied["expression"]


def test_published_package_has_the_real_screening_requirement(db_session):
    """The retired placeholder pair must be gone; the real screening
    requirement/control/evidence must be published."""
    seed_organizations(db_session)
    seed_harborstone_package(db_session)
    published = governance_package_service.get_published_version(
        db_session, HARBORSTONE_ORG_ID, PACKAGE_NAME, PACKAGE_VERSION
    )
    document = governance_package_service.build_package_document(published)

    req_ids = {r["requirement_id"] for r in document["requirements"]}
    ctl_ids = {c["control_id"] for c in document["control_definitions"]}
    ev_types = {e["evidence_type"] for e in document["evidence_requirements"]}
    cond_ids = {c["condition_id"] for c in document["decision_conditions"]}

    assert "REQ-HARBORSTONE-SANCTIONS-SCREENING" in req_ids
    assert "CTL-HARBORSTONE-SANCTIONS-SCREENING" in ctl_ids
    assert "harborstone.sanctions_screening.v1" in ev_types
    assert {"DC-HARBORSTONE-SANCTIONS-CONFIRMED", "DC-HARBORSTONE-SANCTIONS-REVIEW"} <= cond_ids

    assert not any("PLACEHOLDER" in rid for rid in req_ids | ctl_ids)
    assert not any("placeholder" in t for t in ev_types)
