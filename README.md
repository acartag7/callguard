# CallGuard

**Runtime safety for AI agents. Stop agents before they break things.**

> Pre-release — architecture validated, implementation in progress

---

CallGuard is a composable, framework-agnostic middleware that governs AI agent tool execution. It sits between the agent's decision to call a tool and the actual execution — enforcing contracts, budgets, approvals, and audit trails. When a rule is violated, the agent gets an actionable error message and self-corrects automatically.

## Why?

AI agents are executing tools with zero guardrails. They delete databases, push to production, run up API bills, and leak secrets. CallGuard stops them before they break things.

## Features

- [x] **Contracts** — pre/post conditions with retry-with-feedback (agent self-corrects)
- [x] **Hooks** — tool call interception (block, modify, or pass through)
- [x] **Audit Log** — structured event recording for every governance decision
- [ ] **Human Gates** — approval workflows for high-stakes actions (v0.2)
- [ ] **Budget Enforcement** — dollar-based cost limits (v0.2)
- [x] **OpenTelemetry Native** — governance-specific traces and metrics
- [x] **Framework Agnostic** — works with Claude Agent SDK, raw Anthropic/OpenAI SDKs

## Quick Example

```python
from callguard import precondition, Verdict

@precondition("Bash")
def no_force_push(envelope):
    if "--force" in (envelope.bash_command or ""):
        return Verdict.fail(
            "Force push is not allowed. Use regular git push instead."
        )
    return Verdict.pass_()

# Agent tries: git push --force origin main
# CallGuard blocks it and tells the agent why
# Agent self-corrects: git push origin main
```

## Quick Start

```bash
pip install callguard
```

> **Note:** v0.0.1 - project skeleton. Core features shipping March 2026.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full architecture specification.

## What This Is NOT

- **Not prompt injection defense** — CallGuard governs tool execution, not prompt content
- **Not content safety filtering** — use dedicated content moderation for that
- **Not network egress control** — CallGuard operates at the tool call layer, not the network layer
- **Not compliance certification** — helps produce audit artifacts, not a legal guarantee

## License

MIT
