"""AuditEvent, AuditSink protocol, StdoutSink, and FileSink.

Every governance decision produces an AuditEvent that is sent to one or
more AuditSinks for recording. This provides a complete, structured log
of all tool call governance for compliance and debugging.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Protocol

from callguard.types import GovernanceAction


@dataclass
class AuditEvent:
    """A structured record of a governance decision."""

    call_id: str
    tool_name: str
    action: GovernanceAction
    reason: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "action": self.action.value,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
        }


class AuditSink(Protocol):
    """Protocol for audit event destinations."""

    def emit(self, event: AuditEvent) -> None:
        """Record an audit event."""
        ...


class StdoutSink:
    """Writes audit events to stdout as JSON lines."""

    def emit(self, event: AuditEvent) -> None:
        json.dump(event.to_dict(), sys.stdout)
        sys.stdout.write("\n")
        sys.stdout.flush()


class FileSink:
    """Appends audit events to a file as JSON lines."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)

    def emit(self, event: AuditEvent) -> None:
        with self._path.open("a") as f:
            json.dump(event.to_dict(), f)
            f.write("\n")
