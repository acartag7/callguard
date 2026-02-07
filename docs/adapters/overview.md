# Adapter Overview

CallGuard ships six framework adapters that connect the governance pipeline to
popular AI agent frameworks. Every adapter follows the same design principle:
**adapters are thin translation layers**. They convert framework-specific events
into CallGuard envelopes and translate governance decisions back into the format
each framework expects. The adapters contain zero governance logic -- all
allow/deny decisions come from the `GovernancePipeline`.

This architecture means you get identical enforcement semantics regardless of
which framework you use. Switching frameworks requires changing only the adapter
wiring, not your contracts or policies.

## Adapter Lifecycle

Every adapter implements the same six-step lifecycle when a tool call occurs:

```
Framework Event (tool call requested)
        |
        v
  Create Envelope          -- normalize into ToolEnvelope
        |
        v
  Pipeline Pre-Execute     -- evaluate preconditions, session limits, hooks
        |
    +---+---+
    |       |
  DENY    ALLOW
    |       |
    v       v
  Return  Execute Tool     -- framework runs the actual tool
  Denial    |
            v
        Pipeline Post-Execute  -- evaluate postconditions, record result
            |
            v
        Emit Audit Event       -- structured log with redaction
            |
            v
        Framework Response     -- translate back to framework format
```

On **deny**, the adapter short-circuits before the tool runs. The tool callable
is never invoked, and the denial reason is returned in whatever format the
framework expects (a `ToolMessage`, a boolean, a dict, etc.).

On **allow**, the tool executes normally. After execution, the post-execute
phase runs postconditions and records audit events for the outcome.

## Common Adapter API

All six adapters share the same constructor signature:

```python
from callguard import CallGuard, Principal

guard = CallGuard.from_yaml("contracts.yaml")
principal = Principal(user_id="alice", role="sre", ticket_ref="JIRA-1234")

adapter = SomeAdapter(
    guard=guard,                    # required -- the CallGuard instance
    session_id="my-session-123",    # optional -- auto-generated UUID if omitted
    principal=principal,            # optional -- identity context for audit
)
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `guard` | `CallGuard` | required | The configured CallGuard instance holding contracts, limits, and sinks |
| `session_id` | `str \| None` | auto UUID | Groups related tool calls into a session for limit tracking |
| `principal` | `Principal \| None` | `None` | Identity context attached to every audit event in this session |

### Session Management

Each adapter maintains an internal call counter (`_call_index`) and a `Session`
object that tracks attempt and execution counts. Session limits defined in your
contracts (e.g., max 10 tool calls per session) are enforced through this
mechanism. If you pass the same `session_id` to multiple adapter instances
sharing the same `StorageBackend`, their counts accumulate.

### Observe Mode

Every adapter supports observe mode. When the guard is created with
`mode="observe"`, denials are logged as `CALL_WOULD_DENY` audit events but the
tool call is allowed to proceed. This lets you deploy contracts in production
without enforcement to validate behavior before switching to `mode="enforce"`.

## Adapter Reference

| Framework | Adapter Class | Import | Integration Method | Returns |
|-----------|--------------|--------|-------------------|---------|
| Claude Agent SDK | `ClaudeAgentSDKAdapter` | `callguard.adapters.claude_agent_sdk` | `adapter.to_sdk_hooks()` | `dict` with `pre_tool_use` and `post_tool_use` async functions |
| LangChain | `LangChainAdapter` | `callguard.adapters.langchain` | `adapter.as_middleware()` | `@wrap_tool_call` decorated function |
| CrewAI | `CrewAIAdapter` | `callguard.adapters.crewai` | `adapter.register()` | Registers global before/after hooks (no return value) |
| Agno | `AgnoAdapter` | `callguard.adapters.agno` | `adapter.as_tool_hook()` | Wrap-around function for `tool_hooks` parameter |
| Semantic Kernel | `SemanticKernelAdapter` | `callguard.adapters.semantic_kernel` | `adapter.register(kernel)` | Registers `AUTO_FUNCTION_INVOCATION` filter on kernel |
| OpenAI Agents SDK | `OpenAIAgentsAdapter` | `callguard.adapters.openai_agents` | `adapter.as_guardrails()` | `(input_guardrail, output_guardrail)` tuple |

## Choosing an Adapter

Pick the adapter that matches your agent framework:

- **Claude Agent SDK** -- You are building with Anthropic's agent SDK and need
  hook-based governance via `pre_tool_use` / `post_tool_use`.
- **LangChain** -- You are using LangChain agents with the `tool_call_middleware`
  system introduced in `langchain-core >= 0.3`.
- **CrewAI** -- You are using CrewAI crews and want global before/after hooks
  applied to every tool call across all agents in the crew.
- **Agno** -- You are using the Agno framework and need a `tool_hooks`
  compatible function that wraps tool execution.
- **Semantic Kernel** -- You are using Microsoft Semantic Kernel and want to
  register governance as an auto-function-invocation filter on the kernel.
- **OpenAI Agents SDK** -- You are using the OpenAI Agents SDK and want to wire
  governance through the `tool_input_guardrail` / `tool_output_guardrail` system.

If your framework is not listed, use `CallGuard.run()` directly -- it provides
the same governance pipeline without any adapter:

```python
result = await guard.run(
    tool_name="read_file",
    args={"path": "/etc/passwd"},
    tool_callable=my_read_file_fn,
)
```

## Installation Extras

Each adapter has an optional dependency group in `pyproject.toml`:

```bash
pip install callguard[langchain]        # LangChain adapter
pip install callguard[crewai]           # CrewAI adapter
pip install callguard[agno]             # Agno adapter
pip install callguard[semantic-kernel]  # Semantic Kernel adapter
pip install callguard[openai-agents]    # OpenAI Agents SDK adapter
pip install callguard[yaml]             # YAML contract engine (no framework deps)
pip install callguard[all]              # Everything
```

The Claude Agent SDK adapter has no extra dependencies beyond `callguard[yaml]`.
