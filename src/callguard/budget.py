"""Budget, CostModel protocol, and DefaultCostModel.

Budget enforcement tracks the dollar cost of tool calls and blocks
execution when a session or project exceeds its budget.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

from callguard.envelope import ToolEnvelope


class CostModel(Protocol):
    """Protocol for computing the cost of a tool call."""

    def estimate_cost(self, envelope: ToolEnvelope) -> float:
        """Return the estimated cost in USD for executing this tool call."""
        ...


class DefaultCostModel:
    """Default cost model that assigns zero cost to all tool calls.

    Replace with a real cost model that queries provider pricing APIs.
    """

    def estimate_cost(self, envelope: ToolEnvelope) -> float:
        return 0.0


@dataclass
class Budget:
    """Tracks spending against a dollar limit.

    Stub for v0.2 — budget enforcement is not yet active.
    """

    limit_usd: float
    spent_usd: float = 0.0
    _cost_model: CostModel = field(default_factory=DefaultCostModel)

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.limit_usd - self.spent_usd)

    def check(self, envelope: ToolEnvelope) -> bool:
        """Return True if the tool call is within budget."""
        estimated = self._cost_model.estimate_cost(envelope)
        return (self.spent_usd + estimated) <= self.limit_usd

    def record(self, envelope: ToolEnvelope, actual_cost: float | None = None) -> None:
        """Record the cost of an executed tool call."""
        if actual_cost is not None:
            self.spent_usd += actual_cost
        else:
            self.spent_usd += self._cost_model.estimate_cost(envelope)

    def to_dict(self) -> dict[str, Any]:
        return {
            "limit_usd": self.limit_usd,
            "spent_usd": self.spent_usd,
            "remaining_usd": self.remaining_usd,
        }
