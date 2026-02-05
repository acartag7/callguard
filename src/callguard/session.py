"""Session state tracking.

A Session groups related tool calls together and maintains state
across the lifetime of an agent interaction. Session-level contracts
and budgets operate on this scope.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from callguard.envelope import ToolEnvelope


@dataclass
class Session:
    """Tracks state for a single agent session."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tool_calls: list[ToolEnvelope] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def call_count(self) -> int:
        return len(self.tool_calls)

    def record_call(self, envelope: ToolEnvelope) -> None:
        """Record a tool call in this session."""
        self.tool_calls.append(envelope)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "started_at": self.started_at.isoformat(),
            "call_count": self.call_count,
            "metadata": self.metadata,
        }
