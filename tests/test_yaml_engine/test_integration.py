"""End-to-end integration tests for YAML contract engine."""

from __future__ import annotations

from pathlib import Path

import pytest

from edictum import Edictum, EdictumConfigError, EdictumDenied
from edictum.contracts import Verdict, precondition
from edictum.envelope import create_envelope

FIXTURES = Path(__file__).parent / "fixtures"


class NullAuditSink:
    """Collects audit events for inspection."""

    def __init__(self):
        self.events = []

    async def emit(self, event):
        self.events.append(event)


class TestFromYaml:
    def test_creates_guard(self):
        guard = Edictum.from_yaml(FIXTURES / "valid_bundle.yaml")
        assert guard is not None
        assert guard.mode == "enforce"

    def test_policy_version_set(self):
        guard = Edictum.from_yaml(FIXTURES / "valid_bundle.yaml")
        assert guard.policy_version is not None
        assert len(guard.policy_version) == 64  # SHA256 hex

    def test_mode_override(self):
        guard = Edictum.from_yaml(FIXTURES / "valid_bundle.yaml", mode="observe")
        assert guard.mode == "observe"

    def test_limits_from_yaml(self):
        guard = Edictum.from_yaml(FIXTURES / "valid_bundle.yaml")
        assert guard.limits.max_tool_calls == 50
        assert guard.limits.max_attempts == 120

    def test_preconditions_loaded(self):
        guard = Edictum.from_yaml(FIXTURES / "valid_bundle.yaml")
        env = create_envelope("read_file", {"path": ".env"})
        preconditions = guard.get_preconditions(env)
        assert len(preconditions) == 1

    def test_postconditions_loaded(self):
        guard = Edictum.from_yaml(FIXTURES / "valid_bundle.yaml")
        env = create_envelope("some_tool", {})
        postconditions = guard.get_postconditions(env)
        assert len(postconditions) == 1  # wildcard tool

    def test_invalid_yaml_raises(self):
        with pytest.raises(EdictumConfigError):
            Edictum.from_yaml(FIXTURES / "invalid_missing_apiversion.yaml")

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            Edictum.from_yaml(FIXTURES / "nonexistent.yaml")


class TestFromTemplate:
    def test_template_not_found_raises(self):
        with pytest.raises(EdictumConfigError, match="Template 'nonexistent' not found"):
            Edictum.from_template("nonexistent")


class TestEndToEndDeny:
    async def test_yaml_precondition_denies(self):
        sink = NullAuditSink()
        guard = Edictum.from_yaml(
            FIXTURES / "valid_bundle.yaml",
            audit_sink=sink,
        )
        with pytest.raises(EdictumDenied) as exc_info:
            await guard.run(
                "read_file",
                {"path": "/home/.env"},
                lambda path: f"contents of {path}",
            )
        assert ".env" in str(exc_info.value) or "blocked" in str(exc_info.value).lower()

    async def test_yaml_precondition_allows(self):
        sink = NullAuditSink()
        guard = Edictum.from_yaml(
            FIXTURES / "valid_bundle.yaml",
            audit_sink=sink,
        )
        result = await guard.run(
            "read_file",
            {"path": "/home/readme.md"},
            lambda path: f"contents of {path}",
        )
        assert result == "contents of /home/readme.md"

    async def test_non_matching_tool_passes(self):
        sink = NullAuditSink()
        guard = Edictum.from_yaml(
            FIXTURES / "valid_bundle.yaml",
            audit_sink=sink,
        )
        result = await guard.run(
            "write_file",
            {"path": ".env", "content": "test"},
            lambda path, content: "ok",
        )
        assert result == "ok"


class TestPolicyVersionInAudit:
    async def test_policy_version_stamped_on_allow(self):
        sink = NullAuditSink()
        guard = Edictum.from_yaml(
            FIXTURES / "valid_bundle.yaml",
            audit_sink=sink,
        )
        await guard.run(
            "write_file",
            {"path": "readme.md"},
            lambda path: "ok",
        )
        assert len(sink.events) >= 1
        for event in sink.events:
            assert event.policy_version == guard.policy_version

    async def test_policy_version_stamped_on_deny(self):
        sink = NullAuditSink()
        guard = Edictum.from_yaml(
            FIXTURES / "valid_bundle.yaml",
            audit_sink=sink,
        )
        with pytest.raises(EdictumDenied):
            await guard.run(
                "read_file",
                {"path": ".env"},
                lambda path: "contents",
            )
        assert len(sink.events) >= 1
        assert sink.events[0].policy_version == guard.policy_version


class TestYamlVsPythonEquivalence:
    """Verify YAML-loaded guard produces identical verdicts to equivalent Python contracts."""

    async def test_equivalent_verdicts(self):
        # YAML guard
        yaml_sink = NullAuditSink()
        yaml_guard = Edictum.from_yaml(
            FIXTURES / "valid_bundle.yaml",
            audit_sink=yaml_sink,
        )

        # Equivalent Python guard
        @precondition("read_file")
        def block_sensitive_reads(envelope):
            path = envelope.args.get("path", "")
            if any(s in path for s in [".env", ".secret"]):
                return Verdict.fail(f"Sensitive file '{path}' blocked.")
            return Verdict.pass_()

        python_sink = NullAuditSink()
        python_guard = Edictum(
            mode="enforce",
            contracts=[block_sensitive_reads],
            audit_sink=python_sink,
        )

        # Both should deny .env reads
        with pytest.raises(EdictumDenied):
            await yaml_guard.run(
                "read_file",
                {"path": "/home/.env"},
                lambda path: "contents",
            )

        with pytest.raises(EdictumDenied):
            await python_guard.run(
                "read_file",
                {"path": "/home/.env"},
                lambda path: "contents",
            )

        # Both should allow readme reads
        yaml_result = await yaml_guard.run(
            "read_file",
            {"path": "/home/readme.md"},
            lambda path: "readme contents",
        )
        python_result = await python_guard.run(
            "read_file",
            {"path": "/home/readme.md"},
            lambda path: "readme contents",
        )
        assert yaml_result == python_result == "readme contents"

    async def test_observe_mode_yaml(self):
        sink = NullAuditSink()
        guard = Edictum.from_yaml(
            FIXTURES / "valid_bundle.yaml",
            mode="observe",
            audit_sink=sink,
        )
        # Should NOT raise in observe mode, even on .env
        result = await guard.run(
            "read_file",
            {"path": "/home/.env"},
            lambda path: f"contents of {path}",
        )
        assert "contents" in result
        # Audit event should show would_deny
        deny_events = [e for e in sink.events if e.action.value == "call_would_deny"]
        assert len(deny_events) == 1
