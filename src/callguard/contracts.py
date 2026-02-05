"""Verdict and contract decorators: @precondition, @postcondition, @session_contract.

Contracts define rules that tool calls must satisfy. When a precondition
fails, the agent receives the failure reason and can self-correct.
Postconditions validate results after execution.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from callguard.envelope import ToolEnvelope


@dataclass
class Verdict:
    """The result of evaluating a contract against a tool call."""

    passed: bool
    message: str = ""

    @classmethod
    def pass_(cls) -> Verdict:
        """Create a passing verdict."""
        return cls(passed=True)

    @classmethod
    def fail(cls, message: str) -> Verdict:
        """Create a failing verdict with an actionable message for the agent."""
        return cls(passed=False, message=message)


def precondition(tool_name: str) -> Callable:
    """Decorator to register a function as a precondition contract.

    The decorated function receives a ToolEnvelope and returns a Verdict.
    If the Verdict fails, the tool call is blocked and the agent receives
    the failure message to self-correct.

    Args:
        tool_name: The tool this precondition applies to.
    """

    def decorator(fn: Callable[[ToolEnvelope], Verdict]) -> Callable[[ToolEnvelope], Verdict]:
        fn._callguard_contract = "precondition"  # noqa: SLF001
        fn._callguard_tool_name = tool_name  # noqa: SLF001
        return fn

    return decorator


def postcondition(tool_name: str) -> Callable:
    """Decorator to register a function as a postcondition contract.

    The decorated function receives a ToolEnvelope and the tool result,
    and returns a Verdict.

    Args:
        tool_name: The tool this postcondition applies to.
    """

    def decorator(fn: Callable[[ToolEnvelope, Any], Verdict]) -> Callable[[ToolEnvelope, Any], Verdict]:
        fn._callguard_contract = "postcondition"  # noqa: SLF001
        fn._callguard_tool_name = tool_name  # noqa: SLF001
        return fn

    return decorator


def session_contract(fn: Callable) -> Callable:
    """Decorator to register a function as a session-level contract.

    Session contracts are evaluated across the lifetime of a session,
    not per individual tool call. They can enforce invariants like
    'no more than N file deletions per session'.
    """
    fn._callguard_contract = "session"  # noqa: SLF001
    return fn
