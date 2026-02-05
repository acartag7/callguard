"""HookDecision, BeforeHook/AfterHook types, and @hook decorator.

Hooks intercept tool calls before and after execution. A BeforeHook can
block, modify, or pass through a call. An AfterHook can inspect the result
and trigger follow-up actions.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Protocol

from callguard.envelope import ToolEnvelope


class HookAction(Enum):
    """What a hook decides to do with a tool call."""

    ALLOW = "allow"
    BLOCK = "block"
    MODIFY = "modify"


@dataclass
class HookDecision:
    """The result of a hook evaluating a tool call."""

    action: HookAction
    reason: str = ""
    modified_input: dict[str, Any] | None = None

    @classmethod
    def allow(cls) -> HookDecision:
        return cls(action=HookAction.ALLOW)

    @classmethod
    def block(cls, reason: str) -> HookDecision:
        return cls(action=HookAction.BLOCK, reason=reason)

    @classmethod
    def modify(cls, modified_input: dict[str, Any], reason: str = "") -> HookDecision:
        return cls(action=HookAction.MODIFY, modified_input=modified_input, reason=reason)


class BeforeHook(Protocol):
    """Protocol for hooks that run before tool execution."""

    def __call__(self, envelope: ToolEnvelope) -> HookDecision: ...


class AfterHook(Protocol):
    """Protocol for hooks that run after tool execution."""

    def __call__(self, envelope: ToolEnvelope, result: Any) -> None: ...


def hook(tool_name: str | None = None) -> Callable:
    """Decorator to register a function as a before-hook.

    Args:
        tool_name: If provided, the hook only applies to this tool.
                   If None, the hook applies to all tools.
    """

    def decorator(fn: Callable) -> Callable:
        fn._callguard_hook = True  # noqa: SLF001
        fn._callguard_tool_name = tool_name  # noqa: SLF001
        return fn

    return decorator
