"""Restricted deterministic expression engine for applicability evaluation.

This engine evaluates **structured** (JSON/dict) expressions built only from a
closed set of named, side-effect-free operators. It never uses ``eval()``,
``exec()``, ``compile()`` or any form of dynamic Python execution — an
expression is a plain data structure that is walked node by node.

The engine implements three-valued (Kleene) logic. Every expression evaluates
to one of:

* :data:`TriState.TRUE`,
* :data:`TriState.FALSE`,
* :data:`TriState.INDETERMINATE`.

``INDETERMINATE`` is produced when a referenced fact is missing or a comparison
cannot be performed deterministically (for example an unparseable date). It is a
first-class value and is never silently coerced to ``FALSE``; this is what
guarantees that missing context cannot silently produce approval downstream.

Supported operators (see :class:`app.utils.canonical_enums.ExpressionOperator`):

* Comparison: ``equals``, ``not_equals``, ``greater_than``,
  ``greater_than_or_equal``, ``less_than``, ``less_than_or_equal``.
* Membership / string: ``in``, ``not_in``, ``contains``, ``starts_with``.
* Existence: ``exists``, ``not_exists``.
* Dates: ``date_before``, ``date_after``.
* Logical: ``all``, ``any``, ``not``.

Leaf operators reference facts through a dotted ``field`` path (for example
``context.jurisdiction`` or ``intent.parameters.is_international``) resolved
against a nested mapping of runtime facts. A literal operand is supplied as
``value``.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field
from datetime import date, datetime
from enum import Enum
from typing import Any

from app.utils.canonical_enums import ExpressionOperator

# Engine version. Bump when evaluation semantics change in a way that could
# alter results for identical inputs. Recorded on every persisted result.
DETERMINISTIC_ENGINE_VERSION = "1.0.0"


class TriState(str, Enum):
    """Three-valued logic result of a deterministic expression."""

    TRUE = "TRUE"
    FALSE = "FALSE"
    INDETERMINATE = "INDETERMINATE"


class ExpressionError(ValueError):
    """Raised when an expression is structurally invalid or uses an unknown
    operator. This is a *definition* error (the package is malformed), distinct
    from a runtime ``INDETERMINATE`` result caused by missing facts."""


# Sentinel returned by :func:`_resolve_field` when a path is absent.
_MISSING = object()

_COMPARISON_OPERATORS = frozenset(
    {
        ExpressionOperator.EQUALS,
        ExpressionOperator.NOT_EQUALS,
        ExpressionOperator.GREATER_THAN,
        ExpressionOperator.GREATER_THAN_OR_EQUAL,
        ExpressionOperator.LESS_THAN,
        ExpressionOperator.LESS_THAN_OR_EQUAL,
        ExpressionOperator.IN,
        ExpressionOperator.NOT_IN,
        ExpressionOperator.CONTAINS,
        ExpressionOperator.STARTS_WITH,
        ExpressionOperator.DATE_BEFORE,
        ExpressionOperator.DATE_AFTER,
    }
)
_EXISTENCE_OPERATORS = frozenset(
    {ExpressionOperator.EXISTS, ExpressionOperator.NOT_EXISTS}
)
_LOGICAL_OPERATORS = frozenset(
    {ExpressionOperator.ALL, ExpressionOperator.ANY, ExpressionOperator.NOT}
)


@dataclass
class EvaluationOutcome:
    """Result of evaluating an expression against a set of facts.

    ``observed`` is the ordered, de-duplicated list of the runtime facts that
    were actually read while evaluating the expression — the factual basis and
    input references recorded on the persisted result. Each entry is a mapping
    ``{"field": <path>, "value": <observed value>, "present": <bool>}``.
    """

    value: TriState
    observed: list[dict[str, Any]] = dc_field(default_factory=list)
    missing_fields: list[str] = dc_field(default_factory=list)


def _resolve_field(path: str, facts: dict[str, Any]) -> Any:
    """Resolve a dotted ``path`` against nested ``facts``.

    Returns the resolved value, or :data:`_MISSING` if any path segment is
    absent or an intermediate value is not a mapping.
    """
    current: Any = facts
    for segment in path.split("."):
        if isinstance(current, dict) and segment in current:
            current = current[segment]
        else:
            return _MISSING
    return current


def _coerce_datetime(value: Any) -> Any:
    """Best-effort parse of ``value`` into a datetime for date comparisons.

    Returns ``None`` when the value cannot be parsed deterministically.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(text)
        except ValueError:
            return None
    return None


class DeterministicExpressionEngine:
    """Stateless evaluator for restricted deterministic expressions."""

    version: str = DETERMINISTIC_ENGINE_VERSION

    def evaluate(
        self, expression: dict[str, Any], facts: dict[str, Any]
    ) -> EvaluationOutcome:
        """Evaluate ``expression`` against ``facts`` and return the outcome."""
        observed: list[dict[str, Any]] = []
        missing: list[str] = []
        value = self._eval(expression, facts, observed, missing)
        # De-duplicate observed field references while preserving order.
        seen: set[str] = set()
        unique_observed: list[dict[str, Any]] = []
        for entry in observed:
            key = entry["field"]
            if key in seen:
                continue
            seen.add(key)
            unique_observed.append(entry)
        unique_missing = list(dict.fromkeys(missing))
        return EvaluationOutcome(
            value=value, observed=unique_observed, missing_fields=unique_missing
        )

    # -- internal ---------------------------------------------------------- #
    def _eval(
        self,
        node: Any,
        facts: dict[str, Any],
        observed: list[dict[str, Any]],
        missing: list[str],
    ) -> TriState:
        if not isinstance(node, dict):
            raise ExpressionError(f"expression node must be an object: {node!r}")

        raw_op = node.get("op")
        if raw_op is None:
            raise ExpressionError("expression node is missing 'op'")
        try:
            op = ExpressionOperator(raw_op)
        except ValueError as exc:
            raise ExpressionError(f"unsupported operator: {raw_op!r}") from exc

        if op in _LOGICAL_OPERATORS:
            return self._eval_logical(op, node, facts, observed, missing)
        if op in _EXISTENCE_OPERATORS:
            return self._eval_existence(op, node, facts, observed, missing)
        return self._eval_comparison(op, node, facts, observed, missing)

    # -- logical combinators (three-valued) -------------------------------- #
    def _eval_logical(
        self,
        op: ExpressionOperator,
        node: dict[str, Any],
        facts: dict[str, Any],
        observed: list[dict[str, Any]],
        missing: list[str],
    ) -> TriState:
        if op is ExpressionOperator.NOT:
            arg = node.get("arg")
            if arg is None:
                raise ExpressionError("'not' requires an 'arg' expression")
            inner = self._eval(arg, facts, observed, missing)
            if inner is TriState.TRUE:
                return TriState.FALSE
            if inner is TriState.FALSE:
                return TriState.TRUE
            return TriState.INDETERMINATE

        args = node.get("args")
        if not isinstance(args, list) or not args:
            raise ExpressionError(f"'{op.value}' requires a non-empty 'args' list")
        results = [self._eval(a, facts, observed, missing) for a in args]

        if op is ExpressionOperator.ALL:
            # False dominates; otherwise INDETERMINATE if any is indeterminate.
            if any(r is TriState.FALSE for r in results):
                return TriState.FALSE
            if any(r is TriState.INDETERMINATE for r in results):
                return TriState.INDETERMINATE
            return TriState.TRUE

        # ANY: True dominates; otherwise INDETERMINATE if any is indeterminate.
        if any(r is TriState.TRUE for r in results):
            return TriState.TRUE
        if any(r is TriState.INDETERMINATE for r in results):
            return TriState.INDETERMINATE
        return TriState.FALSE

    # -- existence --------------------------------------------------------- #
    def _eval_existence(
        self,
        op: ExpressionOperator,
        node: dict[str, Any],
        facts: dict[str, Any],
        observed: list[dict[str, Any]],
        missing: list[str],
    ) -> TriState:
        path = self._require_field(op, node)
        resolved = _resolve_field(path, facts)
        present = resolved is not _MISSING and resolved is not None
        observed.append(
            {
                "field": path,
                "value": None if resolved is _MISSING else resolved,
                "present": present,
            }
        )
        exists = present
        if op is ExpressionOperator.NOT_EXISTS:
            exists = not exists
        return TriState.TRUE if exists else TriState.FALSE

    # -- comparison / membership / string / date -------------------------- #
    def _eval_comparison(
        self,
        op: ExpressionOperator,
        node: dict[str, Any],
        facts: dict[str, Any],
        observed: list[dict[str, Any]],
        missing: list[str],
    ) -> TriState:
        path = self._require_field(op, node)
        if "value" not in node:
            raise ExpressionError(f"'{op.value}' requires a 'value' operand")
        operand = node["value"]

        resolved = _resolve_field(path, facts)
        present = resolved is not _MISSING
        observed.append(
            {
                "field": path,
                "value": None if resolved is _MISSING else resolved,
                "present": present,
            }
        )
        if not present:
            missing.append(path)
            return TriState.INDETERMINATE

        return self._apply_operator(op, resolved, operand)

    def _apply_operator(
        self, op: ExpressionOperator, left: Any, right: Any
    ) -> TriState:
        """Apply a binary operator, returning INDETERMINATE on any type error.

        The engine is fail-safe: it never raises for a runtime type mismatch,
        it returns ``INDETERMINATE`` so the ambiguity is surfaced explicitly.
        """
        try:
            if op is ExpressionOperator.EQUALS:
                return _b(left == right)
            if op is ExpressionOperator.NOT_EQUALS:
                return _b(left != right)
            if op is ExpressionOperator.IN:
                if not _is_container(right):
                    return TriState.INDETERMINATE
                return _b(left in right)
            if op is ExpressionOperator.NOT_IN:
                if not _is_container(right):
                    return TriState.INDETERMINATE
                return _b(left not in right)
            if op is ExpressionOperator.CONTAINS:
                if not _is_container(left):
                    return TriState.INDETERMINATE
                return _b(right in left)
            if op is ExpressionOperator.STARTS_WITH:
                if not isinstance(left, str) or not isinstance(right, str):
                    return TriState.INDETERMINATE
                return _b(left.startswith(right))
            if op in (
                ExpressionOperator.GREATER_THAN,
                ExpressionOperator.GREATER_THAN_OR_EQUAL,
                ExpressionOperator.LESS_THAN,
                ExpressionOperator.LESS_THAN_OR_EQUAL,
            ):
                return self._apply_ordering(op, left, right)
            if op in (
                ExpressionOperator.DATE_BEFORE,
                ExpressionOperator.DATE_AFTER,
            ):
                return self._apply_date(op, left, right)
        except TypeError:
            return TriState.INDETERMINATE
        # Unreachable — all comparison operators handled above.
        raise ExpressionError(f"unhandled operator: {op.value}")

    @staticmethod
    def _apply_ordering(
        op: ExpressionOperator, left: Any, right: Any
    ) -> TriState:
        # Booleans are excluded from numeric ordering to avoid surprising
        # True>0 style comparisons; treat as non-comparable → INDETERMINATE.
        if isinstance(left, bool) or isinstance(right, bool):
            return TriState.INDETERMINATE
        if op is ExpressionOperator.GREATER_THAN:
            return _b(left > right)
        if op is ExpressionOperator.GREATER_THAN_OR_EQUAL:
            return _b(left >= right)
        if op is ExpressionOperator.LESS_THAN:
            return _b(left < right)
        return _b(left <= right)

    @staticmethod
    def _apply_date(op: ExpressionOperator, left: Any, right: Any) -> TriState:
        left_dt = _coerce_datetime(left)
        right_dt = _coerce_datetime(right)
        if left_dt is None or right_dt is None:
            return TriState.INDETERMINATE
        # Compare naive/aware datetimes on a common footing.
        if (left_dt.tzinfo is None) != (right_dt.tzinfo is None):
            left_dt = left_dt.replace(tzinfo=None)
            right_dt = right_dt.replace(tzinfo=None)
        if op is ExpressionOperator.DATE_BEFORE:
            return _b(left_dt < right_dt)
        return _b(left_dt > right_dt)

    @staticmethod
    def _require_field(op: ExpressionOperator, node: dict[str, Any]) -> str:
        path = node.get("field")
        if not isinstance(path, str) or not path:
            raise ExpressionError(f"'{op.value}' requires a non-empty 'field'")
        return path


def _b(value: bool) -> TriState:
    return TriState.TRUE if value else TriState.FALSE


def _is_container(value: Any) -> bool:
    return isinstance(value, (list, tuple, set, str))


# Module-level singleton — the engine is stateless and safe to share.
default_engine = DeterministicExpressionEngine()
