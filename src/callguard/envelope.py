"""ToolEnvelope dataclass, SideEffect enum, and ToolRegistry.

The ToolEnvelope wraps every tool call with metadata needed for governance
decisions. The SideEffect enum classifies what kind of real-world impact a
tool call may have. The ToolRegistry maps tool names to their side-effect
classifications.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class SideEffect(Enum):
    """Classification of a tool call's real-world impact."""

    NONE = "none"          # Pure read, no state change (e.g., Read, Glob)
    IDEMPOTENT = "idempotent"  # Can be safely retried (e.g., Write with same content)
    REVERSIBLE = "reversible"  # Can be undone (e.g., git commit)
    IRREVERSIBLE = "irreversible"  # Cannot be undone (e.g., rm -rf, API call with side effects)


@dataclass(frozen=True)
class ToolEnvelope:
    """Wraps a tool call with governance metadata.

    Every tool invocation passes through a ToolEnvelope before execution.
    The envelope carries the original call parameters plus context needed
    for contracts, hooks, budgets, and audit.
    """

    tool_name: str
    tool_input: dict[str, Any]
    call_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    session_id: str | None = None
    side_effect: SideEffect = SideEffect.NONE

    @property
    def bash_command(self) -> str | None:
        """Extract the bash command if this is a Bash tool call."""
        if self.tool_name == "Bash":
            return self.tool_input.get("command")
        return None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary for audit/logging."""
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "tool_input": self.tool_input,
            "timestamp": self.timestamp.isoformat(),
            "session_id": self.session_id,
            "side_effect": self.side_effect.value,
        }


class ToolRegistry:
    """Maps tool names to their side-effect classifications.

    Used by the governance pipeline to look up the expected impact
    of a tool call before applying policies.
    """

    def __init__(self) -> None:
        self._registry: dict[str, SideEffect] = {}

    def register(self, tool_name: str, side_effect: SideEffect) -> None:
        """Register a tool with its side-effect classification."""
        self._registry[tool_name] = side_effect

    def get_side_effect(self, tool_name: str) -> SideEffect:
        """Look up the side-effect classification for a tool.

        Returns SideEffect.NONE if the tool is not registered.
        """
        return self._registry.get(tool_name, SideEffect.NONE)

    def register_defaults(self) -> None:
        """Register default side-effect classifications for common tools."""
        defaults = {
            "Read": SideEffect.NONE,
            "Glob": SideEffect.NONE,
            "Grep": SideEffect.NONE,
            "Write": SideEffect.IDEMPOTENT,
            "Edit": SideEffect.IDEMPOTENT,
            "Bash": SideEffect.IRREVERSIBLE,
        }
        for name, effect in defaults.items():
            self._registry.setdefault(name, effect)
