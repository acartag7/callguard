"""Basic tests for ToolEnvelope creation."""

from callguard.envelope import SideEffect, ToolEnvelope, ToolRegistry


class TestToolEnvelope:
    def test_create_envelope(self):
        envelope = ToolEnvelope(
            tool_name="Bash",
            tool_input={"command": "ls -la"},
        )
        assert envelope.tool_name == "Bash"
        assert envelope.tool_input == {"command": "ls -la"}
        assert envelope.call_id  # auto-generated
        assert envelope.timestamp  # auto-generated
        assert envelope.side_effect == SideEffect.NONE

    def test_bash_command_property(self):
        envelope = ToolEnvelope(
            tool_name="Bash",
            tool_input={"command": "git push --force origin main"},
        )
        assert envelope.bash_command == "git push --force origin main"

    def test_bash_command_returns_none_for_non_bash(self):
        envelope = ToolEnvelope(
            tool_name="Read",
            tool_input={"file_path": "/tmp/test.txt"},
        )
        assert envelope.bash_command is None

    def test_to_dict(self):
        envelope = ToolEnvelope(
            tool_name="Write",
            tool_input={"file_path": "/tmp/out.txt", "content": "hello"},
            session_id="test-session",
            side_effect=SideEffect.IDEMPOTENT,
        )
        d = envelope.to_dict()
        assert d["tool_name"] == "Write"
        assert d["session_id"] == "test-session"
        assert d["side_effect"] == "idempotent"

    def test_envelope_is_frozen(self):
        envelope = ToolEnvelope(
            tool_name="Bash",
            tool_input={"command": "echo hi"},
        )
        try:
            envelope.tool_name = "Read"  # type: ignore[misc]
            assert False, "Should have raised FrozenInstanceError"
        except AttributeError:
            pass


class TestToolRegistry:
    def test_register_and_lookup(self):
        registry = ToolRegistry()
        registry.register("Bash", SideEffect.IRREVERSIBLE)
        assert registry.get_side_effect("Bash") == SideEffect.IRREVERSIBLE

    def test_unknown_tool_returns_none(self):
        registry = ToolRegistry()
        assert registry.get_side_effect("UnknownTool") == SideEffect.NONE

    def test_register_defaults(self):
        registry = ToolRegistry()
        registry.register_defaults()
        assert registry.get_side_effect("Read") == SideEffect.NONE
        assert registry.get_side_effect("Bash") == SideEffect.IRREVERSIBLE
        assert registry.get_side_effect("Write") == SideEffect.IDEMPOTENT
