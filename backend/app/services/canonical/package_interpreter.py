"""Deterministic executable-governance-package interpreter.

CompliAGL applies approved, published governance packages to a concrete
(actor, intent, target, context) tuple **deterministically**. This module
defines the interpreter interface and a default implementation that evaluates a
package's decision conditions against a flat dictionary of runtime facts.

No LLM is used for any runtime decision. Condition expressions are evaluated by
a restricted, side-effect-free AST evaluator that supports only boolean logic,
comparisons, membership tests, and literal/attribute lookups — never arbitrary
code execution.
"""

from __future__ import annotations

import ast
import operator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from app.utils.canonical_enums import DecisionOutcome

# Allowed binary comparison operators.
_COMPARATORS = {
    ast.Eq: operator.eq,
    ast.NotEq: operator.ne,
    ast.Lt: operator.lt,
    ast.LtE: operator.le,
    ast.Gt: operator.gt,
    ast.GtE: operator.ge,
    ast.In: lambda a, b: a in b,
    ast.NotIn: lambda a, b: a not in b,
}


class ExpressionError(ValueError):
    """Raised when an expression is malformed or uses unsupported syntax."""


def evaluate_expression(expression: str, context: dict[str, Any]) -> Any:
    """Deterministically evaluate a restricted boolean/comparison expression.

    Supported: names (resolved from ``context``, dotted names via mapping keys),
    literals, ``and``/``or``/``not``, comparisons (``== != < <= > >=``),
    membership (``in`` / ``not in``), and parentheses. Anything else raises
    :class:`ExpressionError`.
    """
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:  # pragma: no cover - defensive
        raise ExpressionError(f"invalid expression: {expression!r}") from exc
    return _eval_node(tree.body, context)


def _eval_node(node: ast.AST, context: dict[str, Any]) -> Any:
    if isinstance(node, ast.BoolOp):
        # Short-circuit like real Python `and`/`or`: a downstream operand
        # referencing a field that doesn't exist for this context (e.g. an
        # intent with no amount_minor) must not be evaluated once the
        # combining operator's result is already determined -- evaluating
        # it eagerly raised TypeError('>=' not supported between NoneType
        # and int) for expressions like `amount_currency == 'USD' and
        # amount_minor >= threshold` on intents with no amount at all.
        if isinstance(node.op, ast.And):
            for value_node in node.values:
                if not _eval_node(value_node, context):
                    return False
            return True
        for value_node in node.values:
            if _eval_node(value_node, context):
                return True
        return False
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, context)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, context)
        for op, comparator in zip(node.ops, node.comparators):
            func = _COMPARATORS.get(type(op))
            if func is None:
                raise ExpressionError(f"unsupported comparator: {type(op).__name__}")
            right = _eval_node(comparator, context)
            if not func(left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Name):
        return context.get(node.id)
    if isinstance(node, ast.Attribute):
        # Dotted access resolves through nested mappings, e.g. intent.amount_minor.
        base = _eval_node(node.value, context)
        if isinstance(base, dict):
            return base.get(node.attr)
        return getattr(base, node.attr, None)
    if isinstance(node, ast.Subscript):
        base = _eval_node(node.value, context)
        key = _eval_node(node.slice, context)
        try:
            return base[key]
        except (KeyError, IndexError, TypeError):
            return None
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        return [_eval_node(elt, context) for elt in node.elts]
    raise ExpressionError(f"unsupported expression element: {type(node).__name__}")


@dataclass
class InterpretationResult:
    """Deterministic outcome of interpreting a package for one context."""

    decision: str
    reason_codes: list[str] = field(default_factory=list)
    matched_condition_id: str | None = None
    evaluated_conditions: list[str] = field(default_factory=list)


@runtime_checkable
class PackageInterpreter(Protocol):
    """Interface every deterministic package interpreter must satisfy."""

    def interpret(
        self, package: dict[str, Any], context: dict[str, Any]
    ) -> InterpretationResult:
        """Apply ``package`` to ``context`` and return a deterministic result."""
        ...


class DeterministicPackageInterpreter:
    """Reference deterministic interpreter.

    Decision conditions are sorted by ``priority`` (ascending, ties broken by
    ``condition_id``) and evaluated in order. The first condition whose
    expression is true and which is ``terminal`` decides the outcome. If no
    condition matches, the default decision is ``DENIED`` (fail-closed).
    """

    default_decision: str = DecisionOutcome.DENIED.value
    default_reason_code: str = "NO_CONDITION_MATCHED"

    def interpret(
        self, package: dict[str, Any], context: dict[str, Any]
    ) -> InterpretationResult:
        conditions = package.get("decision_conditions") or []
        ordered = sorted(
            (c for c in conditions if isinstance(c, dict)),
            key=lambda c: (c.get("priority", 100), str(c.get("condition_id", ""))),
        )

        result = InterpretationResult(
            decision=self.default_decision,
            reason_codes=[self.default_reason_code],
        )

        for condition in ordered:
            cond_id = condition.get("condition_id")
            result.evaluated_conditions.append(str(cond_id))
            expression = condition.get("expression", "")
            try:
                matched = bool(evaluate_expression(expression, context))
            except ExpressionError:
                # A malformed condition is treated as non-matching but recorded;
                # the interpreter never raises at runtime (fail-closed).
                matched = False
            if not matched:
                continue

            result.decision = condition.get(
                "resulting_decision", self.default_decision
            )
            result.reason_codes = [condition.get("reason_code", "MATCHED")]
            result.matched_condition_id = cond_id
            if condition.get("terminal", True):
                return result
        return result
