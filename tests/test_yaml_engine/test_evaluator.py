"""Tests for the YAML condition evaluator."""

from __future__ import annotations

from callguard.envelope import Principal, ToolEnvelope, create_envelope
from callguard.yaml_engine.evaluator import _PolicyError, evaluate_expression

# --- Helpers ---


def _envelope(
    tool_name: str = "read_file",
    args: dict | None = None,
    environment: str = "production",
    principal: Principal | None = None,
) -> ToolEnvelope:
    return create_envelope(
        tool_name=tool_name,
        tool_input=args or {},
        environment=environment,
        principal=principal,
    )


# --- Selector Resolution ---


class TestSelectorResolution:
    def test_environment(self):
        env = _envelope(environment="staging")
        result = evaluate_expression({"environment": {"equals": "staging"}}, env)
        assert result is True

    def test_tool_name(self):
        env = _envelope(tool_name="read_file")
        result = evaluate_expression({"tool.name": {"equals": "read_file"}}, env)
        assert result is True

    def test_args_simple(self):
        env = _envelope(args={"path": "/etc/passwd"})
        result = evaluate_expression({"args.path": {"equals": "/etc/passwd"}}, env)
        assert result is True

    def test_args_nested(self):
        env = _envelope(args={"config": {"timeout": 30}})
        result = evaluate_expression({"args.config.timeout": {"equals": 30}}, env)
        assert result is True

    def test_args_deeply_nested(self):
        env = _envelope(args={"a": {"b": {"c": "deep"}}})
        result = evaluate_expression({"args.a.b.c": {"equals": "deep"}}, env)
        assert result is True

    def test_principal_user_id(self):
        env = _envelope(principal=Principal(user_id="alice"))
        result = evaluate_expression({"principal.user_id": {"equals": "alice"}}, env)
        assert result is True

    def test_principal_role(self):
        env = _envelope(principal=Principal(role="admin"))
        result = evaluate_expression({"principal.role": {"equals": "admin"}}, env)
        assert result is True

    def test_principal_ticket_ref(self):
        env = _envelope(principal=Principal(ticket_ref="JIRA-123"))
        result = evaluate_expression({"principal.ticket_ref": {"equals": "JIRA-123"}}, env)
        assert result is True

    def test_principal_claims(self):
        env = _envelope(principal=Principal(claims={"department": "platform"}))
        result = evaluate_expression(
            {"principal.claims.department": {"equals": "platform"}}, env
        )
        assert result is True

    def test_output_text(self):
        env = _envelope()
        result = evaluate_expression(
            {"output.text": {"contains": "secret"}},
            env,
            output_text="this has a secret in it",
        )
        assert result is True

    def test_output_text_missing(self):
        env = _envelope()
        result = evaluate_expression({"output.text": {"contains": "secret"}}, env)
        assert result is False


# --- Missing Field Semantics ---


class TestMissingFields:
    def test_missing_arg_returns_false(self):
        env = _envelope(args={})
        result = evaluate_expression({"args.nonexistent": {"equals": "x"}}, env)
        assert result is False

    def test_missing_nested_arg_returns_false(self):
        env = _envelope(args={"config": {}})
        result = evaluate_expression({"args.config.timeout": {"equals": 30}}, env)
        assert result is False

    def test_missing_intermediate_key_returns_false(self):
        env = _envelope(args={})
        result = evaluate_expression({"args.config.timeout": {"equals": 30}}, env)
        assert result is False

    def test_no_principal_returns_false(self):
        env = _envelope(principal=None)
        result = evaluate_expression({"principal.role": {"equals": "admin"}}, env)
        assert result is False

    def test_none_principal_field_returns_false(self):
        env = _envelope(principal=Principal(role=None))
        result = evaluate_expression({"principal.role": {"equals": "admin"}}, env)
        assert result is False

    def test_unknown_selector_returns_false(self):
        env = _envelope()
        result = evaluate_expression({"unknown.selector": {"equals": "x"}}, env)
        assert result is False

    def test_unknown_principal_field_returns_false(self):
        env = _envelope(principal=Principal())
        result = evaluate_expression({"principal.unknown": {"equals": "x"}}, env)
        assert result is False


# --- Exists Operator ---


class TestExistsOperator:
    def test_exists_true_when_present(self):
        env = _envelope(args={"path": "/tmp/file"})
        result = evaluate_expression({"args.path": {"exists": True}}, env)
        assert result is True

    def test_exists_true_when_missing(self):
        env = _envelope(args={})
        result = evaluate_expression({"args.path": {"exists": True}}, env)
        assert result is False

    def test_exists_false_when_missing(self):
        env = _envelope(args={})
        result = evaluate_expression({"args.path": {"exists": False}}, env)
        assert result is True

    def test_exists_false_when_present(self):
        env = _envelope(args={"path": "/tmp/file"})
        result = evaluate_expression({"args.path": {"exists": False}}, env)
        assert result is False

    def test_exists_true_when_none(self):
        env = _envelope(principal=Principal(role=None))
        result = evaluate_expression({"principal.role": {"exists": True}}, env)
        assert result is False

    def test_exists_false_when_none(self):
        env = _envelope(principal=Principal(role=None))
        result = evaluate_expression({"principal.role": {"exists": False}}, env)
        assert result is True


# --- Equality Operators ---


class TestEqualityOperators:
    def test_equals_string(self):
        env = _envelope(args={"path": ".env"})
        assert evaluate_expression({"args.path": {"equals": ".env"}}, env) is True
        assert evaluate_expression({"args.path": {"equals": ".secret"}}, env) is False

    def test_equals_number(self):
        env = _envelope(args={"count": 42})
        assert evaluate_expression({"args.count": {"equals": 42}}, env) is True
        assert evaluate_expression({"args.count": {"equals": 43}}, env) is False

    def test_equals_boolean(self):
        env = _envelope(args={"dry_run": True})
        assert evaluate_expression({"args.dry_run": {"equals": True}}, env) is True

    def test_not_equals(self):
        env = _envelope(environment="staging")
        assert evaluate_expression({"environment": {"not_equals": "production"}}, env) is True
        assert evaluate_expression({"environment": {"not_equals": "staging"}}, env) is False


# --- Membership Operators ---


class TestMembershipOperators:
    def test_in_operator(self):
        env = _envelope(principal=Principal(role="sre"))
        assert (
            evaluate_expression(
                {"principal.role": {"in": ["sre", "admin", "senior_engineer"]}}, env
            )
            is True
        )

    def test_in_operator_not_in_list(self):
        env = _envelope(principal=Principal(role="junior"))
        assert (
            evaluate_expression(
                {"principal.role": {"in": ["sre", "admin"]}}, env
            )
            is False
        )

    def test_not_in_operator(self):
        env = _envelope(principal=Principal(role="junior"))
        assert (
            evaluate_expression(
                {"principal.role": {"not_in": ["sre", "admin"]}}, env
            )
            is True
        )

    def test_not_in_operator_is_in_list(self):
        env = _envelope(principal=Principal(role="admin"))
        assert (
            evaluate_expression(
                {"principal.role": {"not_in": ["sre", "admin"]}}, env
            )
            is False
        )


# --- String Operators ---


class TestStringOperators:
    def test_contains(self):
        env = _envelope(args={"path": "/home/user/.env.local"})
        assert evaluate_expression({"args.path": {"contains": ".env"}}, env) is True
        assert evaluate_expression({"args.path": {"contains": ".secret"}}, env) is False

    def test_contains_any(self):
        env = _envelope(args={"path": "/home/.env"})
        assert (
            evaluate_expression(
                {"args.path": {"contains_any": [".env", ".secret"]}}, env
            )
            is True
        )

    def test_contains_any_none_match(self):
        env = _envelope(args={"path": "/home/readme.md"})
        assert (
            evaluate_expression(
                {"args.path": {"contains_any": [".env", ".secret"]}}, env
            )
            is False
        )

    def test_starts_with(self):
        env = _envelope(args={"path": "/etc/config"})
        assert evaluate_expression({"args.path": {"starts_with": "/etc"}}, env) is True
        assert evaluate_expression({"args.path": {"starts_with": "/home"}}, env) is False

    def test_ends_with(self):
        env = _envelope(args={"path": "deploy.yaml"})
        assert evaluate_expression({"args.path": {"ends_with": ".yaml"}}, env) is True
        assert evaluate_expression({"args.path": {"ends_with": ".json"}}, env) is False

    def test_matches(self):
        env = _envelope(args={"command": "rm -rf /tmp"})
        assert (
            evaluate_expression(
                {"args.command": {"matches": r"\brm\s+(-rf?|--recursive)\b"}}, env
            )
            is True
        )

    def test_matches_no_match(self):
        env = _envelope(args={"command": "ls -la"})
        assert (
            evaluate_expression(
                {"args.command": {"matches": r"\brm\s+(-rf?|--recursive)\b"}}, env
            )
            is False
        )

    def test_matches_any(self):
        env = _envelope(args={"command": "mkfs /dev/sda"})
        assert (
            evaluate_expression(
                {"args.command": {"matches_any": [r"\brm\b", r"\bmkfs\b"]}}, env
            )
            is True
        )

    def test_matches_any_none_match(self):
        env = _envelope(args={"command": "echo hello"})
        assert (
            evaluate_expression(
                {"args.command": {"matches_any": [r"\brm\b", r"\bmkfs\b"]}}, env
            )
            is False
        )


# --- Numeric Operators ---


class TestNumericOperators:
    def test_gt(self):
        env = _envelope(args={"count": 10})
        assert evaluate_expression({"args.count": {"gt": 5}}, env) is True
        assert evaluate_expression({"args.count": {"gt": 10}}, env) is False
        assert evaluate_expression({"args.count": {"gt": 15}}, env) is False

    def test_gte(self):
        env = _envelope(args={"count": 10})
        assert evaluate_expression({"args.count": {"gte": 10}}, env) is True
        assert evaluate_expression({"args.count": {"gte": 11}}, env) is False

    def test_lt(self):
        env = _envelope(args={"count": 10})
        assert evaluate_expression({"args.count": {"lt": 15}}, env) is True
        assert evaluate_expression({"args.count": {"lt": 10}}, env) is False

    def test_lte(self):
        env = _envelope(args={"count": 10})
        assert evaluate_expression({"args.count": {"lte": 10}}, env) is True
        assert evaluate_expression({"args.count": {"lte": 9}}, env) is False

    def test_float_comparison(self):
        env = _envelope(args={"score": 3.14})
        assert evaluate_expression({"args.score": {"gt": 3.0}}, env) is True
        assert evaluate_expression({"args.score": {"lt": 4.0}}, env) is True


# --- Type Mismatch ---


class TestTypeMismatch:
    def test_contains_on_number(self):
        env = _envelope(args={"count": 42})
        result = evaluate_expression({"args.count": {"contains": "4"}}, env)
        assert isinstance(result, _PolicyError)
        assert "Type mismatch" in result.message

    def test_gt_on_string(self):
        env = _envelope(args={"name": "alice"})
        result = evaluate_expression({"args.name": {"gt": 5}}, env)
        assert isinstance(result, _PolicyError)

    def test_starts_with_on_number(self):
        env = _envelope(args={"count": 42})
        result = evaluate_expression({"args.count": {"starts_with": "4"}}, env)
        assert isinstance(result, _PolicyError)

    def test_matches_on_number(self):
        env = _envelope(args={"count": 42})
        result = evaluate_expression({"args.count": {"matches": r"\d+"}}, env)
        assert isinstance(result, _PolicyError)

    def test_policy_error_is_truthy(self):
        """PolicyError should be truthy (fail-closed behavior)."""
        error = _PolicyError("test")
        assert bool(error) is True


# --- Boolean Composition ---


class TestBooleanComposition:
    def test_all_true(self):
        env = _envelope(tool_name="deploy", environment="production")
        expr = {
            "all": [
                {"tool.name": {"equals": "deploy"}},
                {"environment": {"equals": "production"}},
            ]
        }
        assert evaluate_expression(expr, env) is True

    def test_all_one_false(self):
        env = _envelope(tool_name="deploy", environment="staging")
        expr = {
            "all": [
                {"tool.name": {"equals": "deploy"}},
                {"environment": {"equals": "production"}},
            ]
        }
        assert evaluate_expression(expr, env) is False

    def test_any_one_true(self):
        env = _envelope(args={"command": "rm -rf /"})
        expr = {
            "any": [
                {"args.command": {"matches": r"\brm\b"}},
                {"args.command": {"matches": r"\bmkfs\b"}},
            ]
        }
        assert evaluate_expression(expr, env) is True

    def test_any_none_true(self):
        env = _envelope(args={"command": "echo hello"})
        expr = {
            "any": [
                {"args.command": {"matches": r"\brm\b"}},
                {"args.command": {"matches": r"\bmkfs\b"}},
            ]
        }
        assert evaluate_expression(expr, env) is False

    def test_not_true(self):
        env = _envelope(principal=Principal(role="junior"))
        expr = {"not": {"principal.role": {"in": ["admin", "sre"]}}}
        assert evaluate_expression(expr, env) is True

    def test_not_false(self):
        env = _envelope(principal=Principal(role="admin"))
        expr = {"not": {"principal.role": {"in": ["admin", "sre"]}}}
        assert evaluate_expression(expr, env) is False

    def test_nested_boolean(self):
        """all + any nested."""
        env = _envelope(
            tool_name="deploy",
            environment="production",
            principal=Principal(role="junior"),
        )
        expr = {
            "all": [
                {"environment": {"equals": "production"}},
                {"not": {"principal.role": {"in": ["senior_engineer", "sre", "admin"]}}},
            ]
        }
        assert evaluate_expression(expr, env) is True

    def test_nested_boolean_denied_by_role(self):
        env = _envelope(
            tool_name="deploy",
            environment="production",
            principal=Principal(role="sre"),
        )
        expr = {
            "all": [
                {"environment": {"equals": "production"}},
                {"not": {"principal.role": {"in": ["senior_engineer", "sre", "admin"]}}},
            ]
        }
        assert evaluate_expression(expr, env) is False

    def test_policy_error_propagates_through_all(self):
        env = _envelope(args={"count": "not_a_number"})
        expr = {
            "all": [
                {"args.count": {"gt": 5}},
            ]
        }
        result = evaluate_expression(expr, env)
        assert isinstance(result, _PolicyError)

    def test_policy_error_propagates_through_any(self):
        env = _envelope(args={"count": "not_a_number"})
        expr = {
            "any": [
                {"args.count": {"gt": 5}},
            ]
        }
        result = evaluate_expression(expr, env)
        assert isinstance(result, _PolicyError)

    def test_policy_error_propagates_through_not(self):
        env = _envelope(args={"count": "not_a_number"})
        expr = {"not": {"args.count": {"gt": 5}}}
        result = evaluate_expression(expr, env)
        assert isinstance(result, _PolicyError)
