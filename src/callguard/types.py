"""Shared types, enums, and protocols for CallGuard."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AuditSink(Protocol):
    """Protocol for audit event consumers."""

    async def emit(self, event: Any) -> None: ...


@dataclass
class HookRegistration:
    """Internal registration for a hook callback."""

    phase: str  # "before" | "after"
    tool: str  # tool name or "*" for all
    callback: Any
    when: Any | None = None


@dataclass
class ToolConfig:
    """Internal tool configuration."""

    name: str
    side_effect: Any
    idempotent: bool = False
