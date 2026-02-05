"""GatePolicy and PendingApproval — human-in-the-loop approval workflows.

Gates pause tool execution and wait for human approval before proceeding.
This module is a stub for v0.2.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class GateStatus(Enum):
    """Status of a gated tool call."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMED_OUT = "timed_out"


@dataclass
class GatePolicy:
    """Defines when a tool call requires human approval.

    Stub for v0.2.
    """

    tool_name: str
    reason: str = ""

    def evaluate(self, tool_input: dict[str, Any]) -> bool:
        """Return True if this tool call requires approval."""
        raise NotImplementedError("GatePolicy will be implemented in v0.2")


@dataclass
class PendingApproval:
    """Represents a tool call waiting for human approval.

    Stub for v0.2.
    """

    call_id: str
    tool_name: str
    tool_input: dict[str, Any]
    status: GateStatus = GateStatus.PENDING

    def approve(self) -> None:
        """Approve the pending tool call."""
        raise NotImplementedError("PendingApproval will be implemented in v0.2")

    def deny(self, reason: str = "") -> None:
        """Deny the pending tool call."""
        raise NotImplementedError("PendingApproval will be implemented in v0.2")
