"""Unit tests for the restricted deterministic expression engine.

These verify every supported operator, three-valued (Kleene) logic, and the
guarantee that a missing fact surfaces as ``INDETERMINATE`` rather than
silently as ``FALSE``. The engine never uses ``eval``/``exec``.
"""

from __future__ import annotations

import pytest

from app.services.canonical.deterministic_expression import (
    DeterministicExpressionEngine,
    ExpressionError,
    TriState,
    default_engine,
)

FACTS = {
    "intent": {
        "amount_minor": 50000,
        "action": "book_travel",
        "parameters": {"is_international": False, "airline": "Delta"},
    },
    "context": {
        "jurisdiction": "US",
        "environment": "PRODUCTION",
        "context_timestamp": "2026-06-01T00:00:00Z",
    },
    "target": {"classification": "AIRLINE", "trust_status": "TRUSTED"},
}


def _val(expr):
    return default_engine.evaluate(expr, FACTS).value


# --------------------------------------------------------------------------- #
# Comparison operators
# --------------------------------------------------------------------------- #
def test_equals_true_and_false():
    assert _val({"op": "equals", "field": "context.jurisdiction", "value": "US"}) is TriState.TRUE
    assert _val({"op": "equals", "field": "context.jurisdiction", "value": "EU"}) is TriState.FALSE


def test_not_equals():
    assert _val({"op": "not_equals", "field": "context.jurisdiction", "value": "EU"}) is TriState.TRUE


def test_numeric_ordering():
    assert _val({"op": "greater_than", "field": "intent.amount_minor", "value": 1000}) is TriState.TRUE
    assert _val({"op": "greater_than_or_equal", "field": "intent.amount_minor", "value": 50000}) is TriState.TRUE
    assert _val({"op": "less_than", "field": "intent.amount_minor", "value": 1000}) is TriState.FALSE
    assert _val({"op": "less_than_or_equal", "field": "intent.amount_minor", "value": 50000}) is TriState.TRUE


def test_boolean_is_not_ordered():
    assert _val(
        {"op": "greater_than", "field": "intent.parameters.is_international", "value": 0}
    ) is TriState.INDETERMINATE


# --------------------------------------------------------------------------- #
# Membership / string
# --------------------------------------------------------------------------- #
def test_in_and_not_in():
    assert _val({"op": "in", "field": "context.jurisdiction", "value": ["US", "CA"]}) is TriState.TRUE
    assert _val({"op": "not_in", "field": "context.jurisdiction", "value": ["EU"]}) is TriState.TRUE


def test_contains_and_starts_with():
    assert _val({"op": "contains", "field": "intent.action", "value": "travel"}) is TriState.TRUE
    assert _val({"op": "starts_with", "field": "intent.action", "value": "book"}) is TriState.TRUE
    assert _val({"op": "starts_with", "field": "intent.action", "value": "cancel"}) is TriState.FALSE


# --------------------------------------------------------------------------- #
# Existence
# --------------------------------------------------------------------------- #
def test_exists_and_not_exists():
    assert _val({"op": "exists", "field": "context.jurisdiction"}) is TriState.TRUE
    assert _val({"op": "exists", "field": "context.missing"}) is TriState.FALSE
    assert _val({"op": "not_exists", "field": "context.missing"}) is TriState.TRUE
    assert _val({"op": "not_exists", "field": "context.jurisdiction"}) is TriState.FALSE


# --------------------------------------------------------------------------- #
# Dates
# --------------------------------------------------------------------------- #
def test_date_before_after():
    assert _val(
        {"op": "date_before", "field": "context.context_timestamp", "value": "2026-12-31T00:00:00Z"}
    ) is TriState.TRUE
    assert _val(
        {"op": "date_after", "field": "context.context_timestamp", "value": "2026-01-01T00:00:00Z"}
    ) is TriState.TRUE


def test_unparseable_date_is_indeterminate():
    facts = {"context": {"context_timestamp": "not-a-date"}}
    assert default_engine.evaluate(
        {"op": "date_before", "field": "context.context_timestamp", "value": "2026-01-01"},
        facts,
    ).value is TriState.INDETERMINATE


# --------------------------------------------------------------------------- #
# Missing fact → INDETERMINATE (never FALSE)
# --------------------------------------------------------------------------- #
def test_missing_field_is_indeterminate():
    outcome = default_engine.evaluate(
        {"op": "equals", "field": "context.risk_tier", "value": "HIGH"}, FACTS
    )
    assert outcome.value is TriState.INDETERMINATE
    assert "context.risk_tier" in outcome.missing_fields


def test_missing_nested_root_is_indeterminate():
    # No 'context' key at all.
    outcome = default_engine.evaluate(
        {"op": "equals", "field": "context.jurisdiction", "value": "US"},
        {"intent": {"action": "x"}},
    )
    assert outcome.value is TriState.INDETERMINATE


# --------------------------------------------------------------------------- #
# Logical combinators (three-valued Kleene logic)
# --------------------------------------------------------------------------- #
def test_all_false_dominates_indeterminate():
    expr = {
        "op": "all",
        "args": [
            {"op": "equals", "field": "context.jurisdiction", "value": "EU"},  # FALSE
            {"op": "equals", "field": "context.missing", "value": 1},  # INDETERMINATE
        ],
    }
    assert _val(expr) is TriState.FALSE


def test_all_true_with_indeterminate_is_indeterminate():
    expr = {
        "op": "all",
        "args": [
            {"op": "equals", "field": "context.jurisdiction", "value": "US"},  # TRUE
            {"op": "equals", "field": "context.missing", "value": 1},  # INDETERMINATE
        ],
    }
    assert _val(expr) is TriState.INDETERMINATE


def test_any_true_dominates():
    expr = {
        "op": "any",
        "args": [
            {"op": "equals", "field": "context.jurisdiction", "value": "US"},  # TRUE
            {"op": "equals", "field": "context.missing", "value": 1},  # INDETERMINATE
        ],
    }
    assert _val(expr) is TriState.TRUE


def test_any_all_false_is_false():
    expr = {
        "op": "any",
        "args": [
            {"op": "equals", "field": "context.jurisdiction", "value": "EU"},
            {"op": "equals", "field": "context.environment", "value": "TEST"},
        ],
    }
    assert _val(expr) is TriState.FALSE


def test_not_preserves_indeterminate():
    assert _val({"op": "not", "arg": {"op": "equals", "field": "context.jurisdiction", "value": "US"}}) is TriState.FALSE
    assert _val({"op": "not", "arg": {"op": "equals", "field": "context.missing", "value": 1}}) is TriState.INDETERMINATE


# --------------------------------------------------------------------------- #
# Malformed expressions raise ExpressionError (definition defect)
# --------------------------------------------------------------------------- #
def test_unknown_operator_raises():
    with pytest.raises(ExpressionError):
        default_engine.evaluate({"op": "regex", "field": "x", "value": "y"}, FACTS)


def test_missing_op_raises():
    with pytest.raises(ExpressionError):
        default_engine.evaluate({"field": "x", "value": "y"}, FACTS)


def test_missing_field_key_raises():
    with pytest.raises(ExpressionError):
        default_engine.evaluate({"op": "equals", "value": "y"}, FACTS)


def test_observed_values_recorded():
    outcome = default_engine.evaluate(
        {"op": "equals", "field": "context.jurisdiction", "value": "US"}, FACTS
    )
    assert outcome.observed == [
        {"field": "context.jurisdiction", "value": "US", "present": True}
    ]


def test_engine_is_deterministic_across_instances():
    expr = {"op": "equals", "field": "context.jurisdiction", "value": "US"}
    a = DeterministicExpressionEngine().evaluate(expr, FACTS)
    b = DeterministicExpressionEngine().evaluate(expr, FACTS)
    assert a.value is b.value is TriState.TRUE
