"""Tests for the HarborStone Demo #3 governance-package seed.

``seed_harborstone_package`` publishes ``build_harborstone_package()``
through the real create -> validate -> approve -> publish lifecycle, scoped
to the ``harborstone-demo`` org, and is idempotent on re-run.

These tests exercise the *seed wiring* only. The package still carries a
placeholder screening control -- see
``PENDING_REVIEW_harborstone_screening_control_placeholder.md`` and
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
    assert published.approved_by == "demo3-step2-seed"


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
