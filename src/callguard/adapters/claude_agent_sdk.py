"""Claude Agent SDK adapter — PreToolUse/PostToolUse hook integration.

This adapter connects CallGuard's governance pipeline to the Claude
Agent SDK's hook system, intercepting tool calls at the PreToolUse
and PostToolUse lifecycle points.
"""

from __future__ import annotations

from typing import Any

from callguard.envelope import ToolEnvelope
from callguard.pipeline import GovernancePipeline


class ClaudeAgentAdapter:
    """Adapter that bridges CallGuard with the Claude Agent SDK.

    Usage:
        adapter = ClaudeAgentAdapter(pipeline)
        # Register with Claude Agent SDK hooks
    """

    def __init__(self, pipeline: GovernancePipeline) -> None:
        self._pipeline = pipeline

    def on_pre_tool_use(self, tool_name: str, tool_input: dict[str, Any]) -> dict[str, Any] | None:
        """Called before a tool is executed.

        Returns None to allow execution, or a dict with an error
        message to block the tool call.
        """
        raise NotImplementedError("ClaudeAgentAdapter will be fully implemented in v0.1")

    def on_post_tool_use(self, tool_name: str, tool_input: dict[str, Any], result: Any) -> None:
        """Called after a tool is executed.

        Used for postcondition checks, audit logging, and budget recording.
        """
        raise NotImplementedError("ClaudeAgentAdapter will be fully implemented in v0.1")
