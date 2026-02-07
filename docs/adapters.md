# Adapter Usage Guide

Code snippets for plugging Edictum into each supported framework. Every adapter takes the same two arguments:

```python
from edictum import Edictum, deny_sensitive_reads, OperationLimits, precondition, Verdict

guard = Edictum(
    contracts=[deny_sensitive_reads()],
    limits=OperationLimits(max_tool_calls=100),
)
```

---

## LangChain

```bash
pip install edictum[langchain]
```

```python
from edictum.adapters.langchain import LangChainAdapter

adapter = LangChainAdapter(guard, session_id="session-lc")
middleware = adapter.as_middleware()

# Pass middleware to your agent
agent = create_react_agent(
    llm,
    tools=tools,
    tool_call_middleware=[middleware],
)
```

`as_middleware()` returns a `@wrap_tool_call` decorated function. Denied calls return a `ToolMessage` with the denial reason so the agent can self-correct.

---

## CrewAI

```bash
pip install edictum[crewai]
```

```python
from edictum.adapters.crewai import CrewAIAdapter

adapter = CrewAIAdapter(guard, session_id="session-crew")
adapter.register()  # registers global before/after hooks

# Then use CrewAI as normal — hooks fire automatically
crew = Crew(agents=[agent], tasks=[task])
crew.kickoff()
```

`register()` attaches global `@before_tool_call` / `@after_tool_call` handlers. Denied calls return `False` from the before-hook, which tells CrewAI to skip execution.

---

## Agno

```bash
pip install edictum[agno]
```

```python
from edictum.adapters.agno import AgnoAdapter

adapter = AgnoAdapter(guard, session_id="session-agno")
hook = adapter.as_tool_hook()

# Pass the hook to your Agno agent
agent = Agent(
    model=OpenAIChat(id="gpt-4o-mini"),
    tools=[...],
    tool_hooks=[hook],
)
```

`as_tool_hook()` returns a wrap-around function that receives `(function_name, function_call, arguments)`. It runs governance, calls the tool if allowed, and returns the result or a `"DENIED: ..."` string.

---

## Semantic Kernel

```bash
pip install edictum[semantic-kernel]
```

```python
from semantic_kernel import Kernel
from edictum.adapters.semantic_kernel import SemanticKernelAdapter

kernel = Kernel()
# ... add plugins/functions to kernel ...

adapter = SemanticKernelAdapter(guard, session_id="session-sk")
adapter.register(kernel)

# Then invoke functions as normal — the filter intercepts them
result = await kernel.invoke(function)
```

`register(kernel)` adds an `AUTO_FUNCTION_INVOCATION` filter. Denied calls set `context.terminate = True` and return the denial reason as the function result.

---

## OpenAI Agents SDK

```bash
pip install edictum[openai-agents]
```

```python
from agents import Agent
from edictum.adapters.openai_agents import OpenAIAgentsAdapter

adapter = OpenAIAgentsAdapter(guard, session_id="session-oai")
input_gr, output_gr = adapter.as_guardrails()

agent = Agent(
    name="file-organizer",
    model="gpt-4o-mini",
    tools=[...],
    input_guardrails=[input_gr],
    output_guardrails=[output_gr],
)
```

`as_guardrails()` returns a `(input_guardrail, output_guardrail)` tuple decorated with `@tool_input_guardrail` / `@tool_output_guardrail`. Denied calls return `ToolGuardrailFunctionOutput.reject_content(reason)`.

---

## Claude Agent SDK

```bash
pip install edictum[yaml]
```

```python
from claude_agent_sdk import Agent
from edictum.adapters.claude_agent_sdk import ClaudeAgentSDKAdapter

adapter = ClaudeAgentSDKAdapter(guard, session_id="session-claude")
hooks = adapter.to_sdk_hooks()

agent = Agent(
    model="claude-haiku-4-5",
    tools=[...],
    hooks=hooks,
)
```

`to_sdk_hooks()` returns `{"pre_tool_use": ..., "post_tool_use": ...}`. Denied calls return a dict with `permissionDecision: "deny"` and the reason.

---

## Common Patterns

### Custom contracts

All adapters share the same `Edictum` instance, so contracts work identically:

```python
@precondition("bash")
def no_destructive_commands(envelope):
    cmd = envelope.args.get("command", "")
    if any(p in cmd for p in ["rm -rf", "mkfs", "dd if="]):
        return Verdict.fail(
            "Destructive command blocked. Use 'mv' instead of deleting."
        )
    return Verdict.pass_()

guard = Edictum(contracts=[no_destructive_commands])
```

### Observe mode

Run the full pipeline without blocking. Denials are logged as `CALL_WOULD_DENY`:

```python
guard = Edictum(
    mode="observe",
    contracts=[...],
    audit_sink=FileAuditSink("audit.jsonl"),
)
```

### Audit to file

```python
from edictum import Edictum, FileAuditSink

guard = Edictum(
    contracts=[...],
    audit_sink=FileAuditSink("audit.jsonl"),
)
```

See [quickstart.md](quickstart.md) for contracts, hooks, session contracts, and redaction.
