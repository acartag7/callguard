# CrewAI Adapter

The `CrewAIAdapter` registers global before/after tool-call hooks with the
CrewAI framework. Every tool call across all agents in a crew passes through
these hooks.

## Installation

```bash
pip install edictum[crewai]
```

## Setup

```python
from edictum import Edictum, Principal
from edictum.adapters.crewai import CrewAIAdapter

guard = Edictum.from_yaml("contracts.yaml")

adapter = CrewAIAdapter(
    guard=guard,
    session_id="crew-session-01",
    principal=Principal(user_id="ops-crew", role="devops"),
)

# Register global hooks -- this must be called before the crew runs
adapter.register()
```

The `register()` method imports CrewAI's `before_tool_call` and
`after_tool_call` decorators and registers the adapter's hook functions as
global handlers. After this call, every tool invocation in the CrewAI runtime
passes through Edictum governance.

## Full Example

```python
from edictum import Edictum, Principal
from edictum.adapters.crewai import CrewAIAdapter
from crewai import Agent, Crew, Task

# Configure governance
guard = Edictum.from_yaml("contracts.yaml")
adapter = CrewAIAdapter(
    guard=guard,
    principal=Principal(user_id="deploy-crew", role="ci"),
)
adapter.register()

# Build crew as usual -- hooks are global
researcher = Agent(
    role="Researcher",
    goal="Find deployment status",
    tools=[status_tool, log_reader_tool],
)

task = Task(
    description="Check the health of the staging deployment",
    agent=researcher,
)

crew = Crew(agents=[researcher], tasks=[task])
result = crew.kickoff()
```

## Hook Behavior

- **Before hook**: `async _before_hook(context) -> bool | None`
    - The `context` object has `.tool_name` and `.tool_input` attributes.
    - Returns `None` to allow the tool call to proceed.
    - Returns `False` to deny. CrewAI interprets `False` as a signal to skip
      tool execution.

- **After hook**: `async _after_hook(context)`
    - The `context` object has `.tool_result` with the tool's return value.
    - Runs postconditions and records the execution in the session.
    - Does not return a value.

## Notes

- **Sequential execution model**: CrewAI executes tools sequentially within a
  crew run. The adapter uses a single-pending slot (not a dict keyed by call ID)
  to correlate before/after events. This is correct for sequential execution but
  would need adaptation if CrewAI ever supports parallel tool calls.

- **Global hooks**: `register()` modifies global state in the CrewAI runtime.
  Call it once before any crew runs. If you create multiple adapters, only the
  last one registered will be active.

## Observe Mode

```python
guard = Edictum.from_yaml("contracts.yaml", mode="observe")
adapter = CrewAIAdapter(guard=guard)
adapter.register()
```

Denials are logged as `CALL_WOULD_DENY` audit events but tool calls proceed
normally.

## Custom Audit Sinks

```python
from edictum.audit import FileAuditSink, RedactionPolicy

redaction = RedactionPolicy()
sink = FileAuditSink("audit.jsonl", redaction=redaction)

guard = Edictum.from_yaml(
    "contracts.yaml",
    audit_sink=sink,
    redaction=redaction,
)

adapter = CrewAIAdapter(guard=guard)
adapter.register()
```
