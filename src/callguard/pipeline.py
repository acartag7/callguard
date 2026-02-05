"""GovernancePipeline — the central orchestrator.

The GovernancePipeline evaluates contracts, hooks, gates, and budgets
in order for each tool call, producing a governance decision and
audit trail.
"""

from __future__ import annotations

from typing import Any

from callguard.audit import AuditEvent, AuditSink
from callguard.envelope import ToolEnvelope
from callguard.types import GovernanceAction


class GovernancePipeline:
    """Orchestrates the full governance evaluation for a tool call.

    Pipeline order:
    1. Contracts (preconditions)
    2. Hooks (before)
    3. Gates (human approval)
    4. Budget check
    5. Execute tool
    6. Contracts (postconditions)
    7. Hooks (after)
    8. Audit
    """

    def __init__(self, sinks: list[AuditSink] | None = None) -> None:
        self._sinks: list[AuditSink] = sinks or []

    def evaluate(self, envelope: ToolEnvelope) -> GovernanceAction:
        """Evaluate all governance rules for a tool call.

        Returns the governance action to take.
        """
        raise NotImplementedError("GovernancePipeline.evaluate will be implemented in v0.1")

    def _emit_audit(self, event: AuditEvent) -> None:
        """Send an audit event to all registered sinks."""
        for sink in self._sinks:
            sink.emit(event)
