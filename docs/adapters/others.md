# Agno, Semantic Kernel, and OpenAI Agents Adapters

This page covers the three remaining framework adapters. Each section includes
installation, setup, a full example, and framework-specific notes.

All adapters share the same constructor signature and lifecycle described in the
[Adapter Overview](overview.md). The differences are in how each framework
exposes hook points and what format it expects for allow/deny signals.

---

## Agno

The `AgnoAdapter` produces a wrap-around hook function compatible with Agno's
`tool_hooks` parameter. Unlike the other adapters, the Agno hook wraps the
entire tool execution -- it receives the callable and is responsible for
invoking it.

### Installation

```bash
pip install callguard[agno]
```

### Setup

```python
from callguard import CallGuard, Principal
from callguard.adapters.agno import AgnoAdapter

guard = CallGuard.from_yaml("contracts.yaml")

adapter = AgnoAdapter(
    guard=guard,
    session_id="agno-session-01",
    principal=Principal(user_id="agno-agent", role="assistant"),
)

hook = adapter.as_tool_hook()
```

### Full Example

```python
from callguard import CallGuard, Principal
from callguard.adapters.agno import AgnoAdapter
from agno import Agent

# Configure governance
guard = CallGuard.from_yaml("contracts.yaml")
adapter = AgnoAdapter(
    guard=guard,
    principal=Principal(user_id="research-agent"),
)

hook = adapter.as_tool_hook()

# Pass the hook to Agno's tool_hooks parameter
agent = Agent(
    model="gpt-4o-mini",
    tools=[search_tool, file_tool],
    tool_hooks=[hook],
)

result = agent.run("Look up the latest quarterly earnings")
```

### Hook Behavior

The hook function has this signature:

```python
def hook(function_name: str, function_call: Callable, arguments: dict) -> result
```

The adapter controls the full lifecycle:

1. Runs pre-execution governance.
2. If allowed, calls `function_call(**arguments)` -- note the **kwargs spread**.
   The tool callable receives keyword arguments, not a single dict.
3. Runs post-execution governance.
4. Returns the tool result on success or `"DENIED: <reason>"` on deny.

### Notes

- **Kwargs spread**: Agno passes tool arguments as a dict, but the adapter
  spreads them with `function_call(**arguments)`. Your tool callables must accept
  keyword arguments, not a single positional dict.

- **Async-to-sync bridging**: Agno's `tool_hooks` are synchronous, but
  CallGuard's pipeline is async. The adapter detects whether an event loop is
  already running:
    - If no loop is running, it uses `asyncio.run()`.
    - If a loop is already running (common in async frameworks), it spins up a
      `ThreadPoolExecutor` with a single worker and runs the async code in a
      fresh event loop on that thread.

- **Async tool support**: If `function_call(**arguments)` returns a coroutine,
  the adapter awaits it automatically.

---

## Semantic Kernel

The `SemanticKernelAdapter` registers an `AUTO_FUNCTION_INVOCATION` filter on a
Semantic Kernel `Kernel` instance. The filter intercepts every auto-invoked
function call and runs CallGuard governance around it.

### Installation

```bash
pip install callguard[semantic-kernel]
```

### Setup

```python
from callguard import CallGuard, Principal
from callguard.adapters.semantic_kernel import SemanticKernelAdapter
from semantic_kernel import Kernel

kernel = Kernel()
guard = CallGuard.from_yaml("contracts.yaml")

adapter = SemanticKernelAdapter(
    guard=guard,
    session_id="sk-session-01",
    principal=Principal(user_id="sk-agent", role="assistant"),
)

# Register the filter on the kernel
adapter.register(kernel)
```

### Full Example

```python
from callguard import CallGuard, Principal
from callguard.adapters.semantic_kernel import SemanticKernelAdapter
from semantic_kernel import Kernel
from semantic_kernel.connectors.ai.open_ai import OpenAIChatCompletion

# Build kernel
kernel = Kernel()
kernel.add_service(OpenAIChatCompletion(service_id="chat", ai_model_id="gpt-4o-mini"))
kernel.add_plugin(file_plugin, "FileOps")
kernel.add_plugin(search_plugin, "Search")

# Configure governance
guard = CallGuard.from_yaml("contracts.yaml")
adapter = SemanticKernelAdapter(
    guard=guard,
    principal=Principal(user_id="analyst", role="data-team"),
)
adapter.register(kernel)

# Use the kernel -- all auto-invoked functions are now governed
settings = kernel.get_prompt_execution_settings_from_service_id("chat")
settings.function_choice_behavior = "auto"

result = await kernel.invoke_prompt(
    "Summarize the contents of report.txt",
    settings=settings,
)
```

### Hook Behavior

The adapter registers a filter using `@kernel.filter(FilterTypes.AUTO_FUNCTION_INVOCATION)`.
Inside the filter:

1. Extracts `context.function.name` and `context.arguments`.
2. Runs pre-execution governance.
3. **On allow**: calls `await next(context)` to let Semantic Kernel execute the
   function, then runs post-execution governance on `context.function_result`.
4. **On deny**: sets `context.function_result` to the denial string and sets
   `context.terminate = True`. The function is never executed, and the kernel
   stops further auto-invocations in the current turn.

### Notes

- **Filter registration**: `adapter.register(kernel)` must be called before
  invoking prompts that trigger auto function calls. The filter is permanently
  registered on the kernel instance.

- **Terminate on deny**: Setting `context.terminate = True` stops the kernel
  from making additional function calls in the same turn. The LLM receives the
  denial message and can decide how to proceed on the next turn.

- **Error detection**: Beyond standard string-based error checking, the adapter
  also inspects Semantic Kernel `FunctionResult` objects for error metadata via
  `result.metadata.get("error")`.

---

## OpenAI Agents SDK

The `OpenAIAgentsAdapter` produces a pair of guardrail functions --
`(input_guardrail, output_guardrail)` -- compatible with the OpenAI Agents SDK's
tool guardrail system.

### Installation

```bash
pip install callguard[openai-agents]
```

### Setup

```python
from callguard import CallGuard, Principal
from callguard.adapters.openai_agents import OpenAIAgentsAdapter

guard = CallGuard.from_yaml("contracts.yaml")

adapter = OpenAIAgentsAdapter(
    guard=guard,
    session_id="oai-session-01",
    principal=Principal(user_id="oai-agent", role="assistant"),
)

input_guardrail, output_guardrail = adapter.as_guardrails()
```

### Full Example

```python
from callguard import CallGuard, Principal
from callguard.adapters.openai_agents import OpenAIAgentsAdapter
from agents import Agent

# Configure governance
guard = CallGuard.from_yaml("contracts.yaml")
adapter = OpenAIAgentsAdapter(
    guard=guard,
    principal=Principal(user_id="support-agent", role="tier-1"),
)

input_gr, output_gr = adapter.as_guardrails()

# Build agent with guardrails
agent = Agent(
    name="Support Agent",
    model="gpt-4o-mini",
    tools=[ticket_tool, knowledge_base_tool],
    input_guardrails=[input_gr],
    output_guardrails=[output_gr],
)

result = await agent.run("Look up ticket SUPPORT-4521 and summarize the issue")
```

### Guardrail Behavior

#### Input guardrail (pre-execution)

The input guardrail fires before each tool call. It extracts the tool name and
arguments from the guardrail data:

```python
tool_name = data.context.tool_name
tool_arguments = json.loads(data.context.tool_arguments)
```

- **On allow**: returns `ToolGuardrailFunctionOutput.allow()`.
- **On deny**: returns `ToolGuardrailFunctionOutput.reject_content(reason)`.

#### Output guardrail (post-execution)

The output guardrail fires after tool execution. It runs postconditions and
records the execution. The output guardrail always returns
`ToolGuardrailFunctionOutput.allow()` -- post-execution governance produces
audit events and warnings but does not block the response.

### Notes

- **FIFO correlation**: The OpenAI Agents SDK does not pass a shared
  `tool_use_id` between input and output guardrails. The adapter correlates them
  using insertion-order iteration over its pending dict (`next(iter(self._pending))`).
  This works correctly for sequential tool execution but assumes tools are not
  invoked in parallel within a single agent run. If the SDK ever supports
  parallel tool calls, a proper correlation key would be needed.

- **Input guardrails vs output guardrails**: The SDK treats these as separate
  function types decorated with `@tool_input_guardrail` and
  `@tool_output_guardrail` respectively. Both are passed to the `Agent`
  constructor as lists.

---

## Common Patterns

These patterns apply to all four adapters on this page.

### Observe Mode

All adapters support observe mode for safe production rollout:

```python
guard = CallGuard.from_yaml("contracts.yaml", mode="observe")
adapter = SomeAdapter(guard=guard)
```

Denials are logged as `CALL_WOULD_DENY` audit events but tool calls proceed
normally.

### Custom Audit Sinks

Route audit output to a file with automatic redaction:

```python
from callguard.audit import FileAuditSink, RedactionPolicy

redaction = RedactionPolicy()
sink = FileAuditSink("audit.jsonl", redaction=redaction)

guard = CallGuard.from_yaml(
    "contracts.yaml",
    audit_sink=sink,
    redaction=redaction,
)
```

### Principal for Identity Context

Attach identity information to every audit event in a session:

```python
from callguard import Principal

principal = Principal(
    user_id="alice",
    role="sre",
    ticket_ref="JIRA-1234",
    claims={"department": "platform", "clearance": "l2"},
)

adapter = SomeAdapter(guard=guard, principal=principal)
```

The principal is included in every `AuditEvent` emitted by the adapter. Use it
to trace which user or service triggered each tool call in your audit logs.
