"""``decision_service._evidence_claims_facts`` -- the generic mechanism that
surfaces normalized evidence claims into the decision context so a package's
*decision* conditions can key off a concrete evidence signal (e.g. a sanctions
screening ``result``), not just the coarse assessment verdict.

The HarborStone screening routing that uses it end-to-end is covered in
``test_harborstone_screening_pipeline.py``; this pins the helper itself.
"""

from __future__ import annotations

import json
import types

from app.services.canonical import decision_service


class _Norm:
    def __init__(self, req_id, claims):
        self.evidence_requirement_id = req_id
        self.normalized_claims = json.dumps(claims)


class _FakeRepo:
    def __init__(self, items):
        self._items = items

    def __call__(self, db):  # repo is constructed as Repo(db)
        return self

    def list_for_job(self, org, job_id):
        return list(self._items)


def _patch_repo(monkeypatch, items):
    monkeypatch.setattr(
        decision_service, "NormalizedEvidenceRepository", _FakeRepo(items)
    )


def test_returns_empty_when_no_evidence_package(monkeypatch):
    _patch_repo(monkeypatch, [])
    assert decision_service._evidence_claims_facts(None, "org", None) == {}


def test_returns_empty_when_package_has_no_collection_job(monkeypatch):
    _patch_repo(monkeypatch, [_Norm("EV-1", {"result": "NO_MATCH"})])
    pkg = types.SimpleNamespace(collection_job_id=None)
    assert decision_service._evidence_claims_facts(None, "org", pkg) == {}


def test_claims_keyed_by_requirement_id(monkeypatch):
    _patch_repo(
        monkeypatch,
        [
            _Norm("EV-SCREENING", {"result": "POTENTIAL_MATCH",
                                   "requires_human_review": True}),
            _Norm("EV-OTHER", {"foo": "bar"}),
        ],
    )
    pkg = types.SimpleNamespace(collection_job_id="job-1")
    facts = decision_service._evidence_claims_facts(None, "org", pkg)
    assert facts["EV-SCREENING"]["result"] == "POTENTIAL_MATCH"
    assert facts["EV-SCREENING"]["requires_human_review"] is True
    assert facts["EV-OTHER"] == {"foo": "bar"}


def test_first_item_wins_per_requirement(monkeypatch):
    _patch_repo(
        monkeypatch,
        [
            _Norm("EV-SCREENING", {"result": "NO_MATCH"}),
            _Norm("EV-SCREENING", {"result": "CONFIRMED_MATCH"}),
        ],
    )
    pkg = types.SimpleNamespace(collection_job_id="job-1")
    facts = decision_service._evidence_claims_facts(None, "org", pkg)
    assert facts["EV-SCREENING"]["result"] == "NO_MATCH"


def test_non_dict_claims_normalize_to_empty(monkeypatch):
    _patch_repo(monkeypatch, [_Norm("EV-SCREENING", ["not", "a", "dict"])])
    pkg = types.SimpleNamespace(collection_job_id="job-1")
    facts = decision_service._evidence_claims_facts(None, "org", pkg)
    assert facts["EV-SCREENING"] == {}
