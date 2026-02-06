"""GovernancePipeline — single source of governance logic."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from callguard.envelope import SideEffect, ToolEnvelope
from callguard.hooks import HookResult
from callguard.session import Session

if TYPE_CHECKING:
    from callguard import CallGuard


@dataclass
class PreDecision:
    """Result of pre-execution governance evaluation."""

    action: str  # "allow" | "deny"
    reason: str | None = None
    decision_source: str | None = None
    decision_name: str | None = None
    hooks_evaluated: list[dict] = field(default_factory=list)
    contracts_evaluated: list[dict] = field(default_factory=list)


@dataclass
class PostDecision:
    """Result of post-execution governance evaluation."""

    tool_success: bool
    postconditions_passed: bool
    warnings: list[str] = field(default_factory=list)
    contracts_evaluated: list[dict] = field(default_factory=list)


class GovernancePipeline:
    """Orchestrates all governance checks.

    This is the single source of truth for governance logic.
    Adapters call pre_execute() and post_execute(), then translate
    the structured results into framework-specific formats.
    """

    def __init__(self, guard: CallGuard):
        self._guard = guard

    async def pre_execute(
        self,
        envelope: ToolEnvelope,
        session: Session,
    ) -> PreDecision:
        """Run all pre-execution governance checks."""
        hooks_evaluated: list[dict] = []
        contracts_evaluated: list[dict] = []

        # 1. Attempt limit
        attempt_count = await session.attempt_count()
        if attempt_count > self._guard.limits.max_attempts:
            return PreDecision(
                action="deny",
                reason=f"Attempt limit reached ({self._guard.limits.max_attempts}). "
                "Agent may be stuck in a retry loop. Stop and reassess.",
                decision_source="attempt_limit",
                decision_name="max_attempts",
                hooks_evaluated=hooks_evaluated,
                contracts_evaluated=contracts_evaluated,
            )

        # 2. Before hooks
        for hook_reg in self._guard.get_hooks("before", envelope):
            if hook_reg.when and not hook_reg.when(envelope):
                continue
            decision = hook_reg.callback(envelope)
            if asyncio.iscoroutine(decision):
                decision = await decision

            hook_record = {
                "name": getattr(hook_reg.callback, "__name__", "anonymous"),
                "result": decision.result.value,
                "reason": decision.reason,
            }
            hooks_evaluated.append(hook_record)

            if decision.result == HookResult.DENY:
                return PreDecision(
                    action="deny",
                    reason=decision.reason,
                    decision_source="hook",
                    decision_name=hook_record["name"],
                    hooks_evaluated=hooks_evaluated,
                    contracts_evaluated=contracts_evaluated,
                )

        # 3. Preconditions
        for contract in self._guard.get_preconditions(envelope):
            verdict = contract(envelope)
            if asyncio.iscoroutine(verdict):
                verdict = await verdict

            contract_record = {
                "name": getattr(contract, "__name__", "anonymous"),
                "type": "precondition",
                "passed": verdict.passed,
                "message": verdict.message,
            }
            contracts_evaluated.append(contract_record)

            if not verdict.passed:
                return PreDecision(
                    action="deny",
                    reason=verdict.message,
                    decision_source="precondition",
                    decision_name=contract_record["name"],
                    hooks_evaluated=hooks_evaluated,
                    contracts_evaluated=contracts_evaluated,
                )

        # 4. Session contracts
        for contract in self._guard.get_session_contracts():
            verdict = contract(session)
            if asyncio.iscoroutine(verdict):
                verdict = await verdict

            contract_record = {
                "name": getattr(contract, "__name__", "anonymous"),
                "type": "session_contract",
                "passed": verdict.passed,
                "message": verdict.message,
            }
            contracts_evaluated.append(contract_record)

            if not verdict.passed:
                return PreDecision(
                    action="deny",
                    reason=verdict.message,
                    decision_source="session_contract",
                    decision_name=contract_record["name"],
                    hooks_evaluated=hooks_evaluated,
                    contracts_evaluated=contracts_evaluated,
                )

        # 5. Execution limits
        exec_count = await session.execution_count()
        if exec_count >= self._guard.limits.max_tool_calls:
            return PreDecision(
                action="deny",
                reason=f"Execution limit reached ({self._guard.limits.max_tool_calls} calls). "
                "Summarize progress and stop.",
                decision_source="operation_limit",
                decision_name="max_tool_calls",
                hooks_evaluated=hooks_evaluated,
                contracts_evaluated=contracts_evaluated,
            )

        # Per-tool limits
        if envelope.tool_name in self._guard.limits.max_calls_per_tool:
            tool_count = await session.tool_execution_count(envelope.tool_name)
            tool_limit = self._guard.limits.max_calls_per_tool[envelope.tool_name]
            if tool_count >= tool_limit:
                return PreDecision(
                    action="deny",
                    reason=f"Per-tool limit: {envelope.tool_name} called "
                    f"{tool_count} times (limit: {tool_limit}).",
                    decision_source="operation_limit",
                    decision_name=f"max_calls_per_tool:{envelope.tool_name}",
                    hooks_evaluated=hooks_evaluated,
                    contracts_evaluated=contracts_evaluated,
                )

        # 6. All checks passed
        return PreDecision(
            action="allow",
            hooks_evaluated=hooks_evaluated,
            contracts_evaluated=contracts_evaluated,
        )

    async def post_execute(
        self,
        envelope: ToolEnvelope,
        tool_response: Any,
        tool_success: bool,
    ) -> PostDecision:
        """Run all post-execution governance checks."""
        warnings: list[str] = []
        contracts_evaluated: list[dict] = []

        # 1. Postconditions (observe-only in v0.0.1)
        for contract in self._guard.get_postconditions(envelope):
            verdict = contract(envelope, tool_response)
            if asyncio.iscoroutine(verdict):
                verdict = await verdict

            contract_record = {
                "name": getattr(contract, "__name__", "anonymous"),
                "type": "postcondition",
                "passed": verdict.passed,
                "message": verdict.message,
            }
            contracts_evaluated.append(contract_record)

            if not verdict.passed:
                if envelope.side_effect in (SideEffect.PURE, SideEffect.READ):
                    warnings.append(f"\u26a0\ufe0f {verdict.message} Consider retrying.")
                else:
                    warnings.append(
                        f"\u26a0\ufe0f {verdict.message} "
                        "Tool already executed \u2014 assess before proceeding."
                    )

        # 2. After hooks
        for hook_reg in self._guard.get_hooks("after", envelope):
            if hook_reg.when and not hook_reg.when(envelope):
                continue
            result = hook_reg.callback(envelope, tool_response)
            if asyncio.iscoroutine(result):
                await result

        postconditions_passed = all(c["passed"] for c in contracts_evaluated) if contracts_evaluated else True

        return PostDecision(
            tool_success=tool_success,
            postconditions_passed=postconditions_passed,
            warnings=warnings,
            contracts_evaluated=contracts_evaluated,
        )
