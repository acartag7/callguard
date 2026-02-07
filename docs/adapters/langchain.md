# LangChain Adapter

The `LangChainAdapter` connects Edictum to LangChain agents through the
`tool_call_middleware` system. It produces a `@wrap_tool_call` decorated function
that intercepts every tool invocation, runs governance checks, and returns a
`ToolMessage` denial when a call is blocked.

## Installation

```bash
pip install edictum[langchain]
```

This installs `langchain-core >= 0.3`, which provides the `wrap_tool_call`
middleware decorator.

## Setup

### 1. Create a Edictum instance

```python
from edictum import Edictum, Principal

# From YAML contracts
guard = Edictum.from_yaml("contracts.yaml")

# Or from a built-in template
guard = Edictum.from_template("research-agent")

# Or with Python contracts
from edictum import deny_sensitive_reads
guard = Edictum(contracts=[deny_sensitive_reads()])
```

### 2. Create the adapter and get the middleware

```python
from edictum.adapters.langchain import LangChainAdapter

principal = Principal(user_id="alice", role="analyst")

adapter = LangChainAdapter(
    guard=guard,
    principal=principal,
)

middleware = adapter.as_middleware()
```

### 3. Pass the middleware to your agent

```python
agent = create_react_agent(
    model=llm,
    tools=tools,
    tool_call_middleware=[middleware],
)
```

## Full Working Example

```python
from edictum import Edictum, Principal
from edictum.adapters.langchain import LangChainAdapter
from langchain_openai import ChatOpenAI
from langchain.agents import create_react_agent

# Configure governance
guard = Edictum.from_yaml("contracts.yaml")

# Create adapter with identity
adapter = LangChainAdapter(
    guard=guard,
    session_id="research-session-01",
    principal=Principal(user_id="researcher", role="analyst"),
)

# Get the middleware function
middleware = adapter.as_middleware()

# Build the LangChain agent with governance
llm = ChatOpenAI(model="gpt-4o-mini")
tools = [search_tool, calculator_tool, file_reader_tool]

agent = create_react_agent(
    model=llm,
    tools=tools,
    tool_call_middleware=[middleware],
)

# Run -- tool calls are now governed
result = agent.invoke({"messages": [("user", "Summarize the Q3 report")]})
```

## Middleware Behavior

### Pre-check

Before each tool call, the middleware runs the governance pipeline. It extracts
the tool name, arguments, and call ID from the LangChain `ToolCallRequest`:

```python
tool_name = request.tool_call["name"]
tool_args = request.tool_call["args"]
tool_call_id = request.tool_call["id"]
```

**On allow**, the middleware returns `None`, signaling LangChain to proceed with
the tool call via the handler.

**On deny**, the middleware returns a `ToolMessage` with the denial reason:

```python
ToolMessage(content="DENIED: File /etc/shadow is in the sensitive path denylist", tool_call_id="call_abc123")
```

LangChain treats this as the tool's response. The LLM sees the denial message
and can adjust its behavior accordingly.

### Post-check

After the tool executes, the middleware runs postconditions and records the
execution in the session. Postcondition results are logged to the audit sink but
do not modify the tool's return value.

## Known Limitation: Event Loops

The LangChain middleware interface is synchronous, but Edictum's governance
pipeline is async. The adapter bridges this gap using
`asyncio.get_event_loop().run_until_complete()`.

**This will raise a `RuntimeError` if an asyncio event loop is already running**
in the current thread. This can happen when:

- Running inside a Jupyter notebook
- Running inside an async web framework (FastAPI, Starlette)
- Running inside any context that already has an active event loop

Workarounds:

1. **Use `nest_asyncio`** to allow nested event loops:
   ```python
   import nest_asyncio
   nest_asyncio.apply()
   ```

2. **Run the agent in a separate thread** that does not have an active event
   loop.

3. **Use `Edictum.run()` directly** in an async context instead of going
   through the LangChain middleware.

## Observe Mode

Deploy contracts in observation mode to see what would be denied without
blocking any tool calls:

```python
guard = Edictum.from_yaml("contracts.yaml", mode="observe")
adapter = LangChainAdapter(guard=guard)
middleware = adapter.as_middleware()
```

In observe mode, the middleware always returns `None` (allow), even for calls
that would be denied. `CALL_WOULD_DENY` audit events are emitted so you can
review enforcement behavior before enabling it.

## Custom Audit Sinks

Route audit events to a file instead of stdout:

```python
from edictum.audit import FileAuditSink, RedactionPolicy

redaction = RedactionPolicy()
sink = FileAuditSink("langchain-audit.jsonl", redaction=redaction)

guard = Edictum.from_yaml(
    "contracts.yaml",
    audit_sink=sink,
    redaction=redaction,
)

adapter = LangChainAdapter(guard=guard)
```

Every governed tool call produces structured audit events. The `RedactionPolicy`
scrubs sensitive values (API keys, tokens, passwords) from the logged arguments
automatically.
