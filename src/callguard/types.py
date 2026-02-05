"""Shared types, enums, and protocols used across CallGuard modules."""

from __future__ import annotations

from enum import Enum
from typing import Any, Protocol


class ToolName(str):
    """A tool name identifier (e.g., 'Bash', 'Read', 'Write')."""


class GovernanceAction(Enum):
    """Actions that the governance pipeline can take on a tool call."""

    ALLOW = "allow"
    BLOCK = "block"
    MODIFY = "modify"
    PENDING = "pending"


class Serializable(Protocol):
    """Protocol for objects that can be serialized to a dictionary."""

    def to_dict(self) -> dict[str, Any]: ...
