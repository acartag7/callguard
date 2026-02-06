# CallGuard Contract Schema — v1 Specification

> **Status:** FINAL — ready for implementation
> **Date:** 2026-02-06
> **Compiles to:** existing `@precondition`, `@postcondition`, `@session_contract`, `OperationLimits`

---

## 1. Document Structure

```yaml
apiVersion: callguard/v1
kind: ContractBundle

metadata:
  name: string          # required, identifier for this bundle
  description: string   # optional

defaults:
  mode: enforce         # required: enforce | observe

contracts:              # required, min 1 item
  - <Contract>
```

### Design decisions
- **No `include`/composition** in v1. One file per CallGuard instance. Pass multiple files to `from_yaml()` for explicit merging.
- **No `on_error`** config. Fail-closed per rule is hardcoded behavior (see §6).
- **No `case_insensitive`** default. All matching is case-sensitive. Case-insensitive operators may be added in v1.1.
- **Bundle hash:** SHA256 of the raw YAML bytes, stamped as `policy_version` on every `AuditEvent` and OTel span attribute.

---

## 2. Contract Types

Every contract has a common base plus type-specific fields.

### Common fields (all types)

Field | Type | Required | Default | Notes
---|---|---|---|---
`id` | string | yes | — | Unique within bundle. Slug format recommended: `[a-z0-9-]+`
`type` | `pre` \| `post` \| `session` | yes | — | Discriminator
`enabled` | bool | no | `true` | `false` = skip during evaluation, still appears in validation
`mode` | `enforce` \| `observe` | no | `defaults.mode` | Per-rule override
`then` | Then | yes | — | Action block (see §4)

### 2.1 Precondition (`type: pre`)

Evaluated before tool execution. Compiles to `@precondition(tool, when=)`.

Field | Type | Required | Notes
---|---|---|---
`tool` | string | yes | Tool name or `"*"` for all tools
`when` | Expression | yes | Boolean expression (see §3)

**Constraints:**
- `then.effect` MUST be `deny`
- `output.text` selector is INVALID (tool hasn't run yet)
- `mode: observe` downgrades deny → `CALL_WOULD_DENY` (audit only, no blocking)

```yaml
- id: block-sensitive-reads
  type: pre
  tool: read_file
  when:
    args.path:
      contains_any: [".env", ".secret", "kubeconfig", "credentials"]
  then:
    effect: deny
    message: "Sensitive file '{args.path}' blocked. Skip and continue."
    tags: [secrets, dlp]
```

### 2.2 Postcondition (`type: post`)

Evaluated after tool execution. Compiles to `@postcondition(tool, when=)`.

Field | Type | Required | Notes
---|---|---|---
`tool` | string | yes | Tool name or `"*"` for all tools
`when` | Expression | yes | Boolean expression (see §3)

**Constraints:**
- `then.effect` MUST be `warn` (tool already ran; cannot block)
- `effect: deny` on a postcondition is a **validation error**

```yaml
- id: pii-in-output
  type: post
  tool: "*"
  when:
    output.text:
      matches_any: ['\b\d{3}-\d{2}-\d{4}\b']
  then:
    effect: warn
    message: "PII detected in output. Redact before using."
    tags: [pii]
```

### 2.3 Session contract (`type: session`)

Evaluated before every tool call as a session-level gate. Compiles to `@session_contract` + `OperationLimits`.

Field | Type | Required | Notes
---|---|---|---
`limits` | SessionLimits | yes | At least one limit required
`tool` | — | INVALID | Session contracts are tool-agnostic
`when` | — | INVALID | No condition DSL for sessions in v1

**SessionLimits:**

Field | Type | Required | Notes
---|---|---|---
`max_tool_calls` | int (≥1) | no* | Total execution cap
`max_attempts` | int (≥1) | no* | Total attempt cap (including denied)
`max_calls_per_tool` | map[string, int≥1] | no* | Per-tool execution caps

*At least one of these must be present.

**Constraints:**
- `then.effect` MUST be `deny`
- Budget tracking deferred to v1.1

```yaml
- id: session-limits
  type: session
  limits:
    max_tool_calls: 25
    max_attempts: 60
    max_calls_per_tool:
      send_slack_message: 10
  then:
    effect: deny
    message: "Session limit reached. Summarize and stop."
    tags: [rate-limit]
```

---

## 3. Expression Grammar (`when`)

An Expression is exactly one of:

### Boolean nodes

```yaml
all: [Expression, ...]    # AND — all must be true. Min 1 item.
any: [Expression, ...]    # OR  — at least one must be true. Min 1 item.
not: Expression            # negation
```

### Leaf node

```yaml
<selector>:
  <operator>: <value>
```

Exactly one selector key, exactly one operator per leaf.

### 3.1 Field Selectors

Selector | Runtime type | Source | Available in
---|---|---|---
`environment` | string | `ToolEnvelope.environment` | pre, post
`tool.name` | string | `ToolEnvelope.tool_name` | pre, post
`args.<key>` | any | `ToolEnvelope.args[key]` | pre, post
`args.<key>.<subkey>` | any | nested arg access | pre, post
`principal.user_id` | string\|null | `Principal.user_id` | pre, post
`principal.service_id` | string\|null | `Principal.service_id` | pre, post
`principal.org_id` | string\|null | `Principal.org_id` | pre, post
`principal.role` | string\|null | `Principal.role` | pre, post
`principal.ticket_ref` | string\|null | `Principal.ticket_ref` | pre, post
`principal.claims.<key>` | any | `Principal.claims[key]` | pre, post
`output.text` | string | stringified tool response | **post only**

**Missing field:** evaluates to `false` (rule doesn't fire). Not an error.

**Nested args:** `args.config.timeout` resolves `envelope.args["config"]["timeout"]`. If any intermediate key is missing, evaluates to `false`.

### 3.2 Operators

#### Presence

Operator | Selector type | Value type | Semantics
---|---|---|---
`exists` | any | `true` \| `false` | `true`: field is present AND not null. `false`: field is absent OR null.

#### Equality

Operator | Selector type | Value type | Semantics
---|---|---|---
`equals` | scalar | scalar | Strict equality (`==`)
`not_equals` | scalar | scalar | Strict inequality (`!=`)

#### Membership

Operator | Selector type | Value type | Semantics
---|---|---|---
`in` | scalar | array | Selector value appears in array
`not_in` | scalar | array | Selector value does NOT appear in array

#### String

Operator | Selector type | Value type | Semantics
---|---|---|---
`contains` | string | string | `value in selector_value`
`contains_any` | string | array[string] | Any value is a substring
`starts_with` | string | string | `selector_value.startswith(value)`
`ends_with` | string | string | `selector_value.endswith(value)`
`matches` | string | string (regex) | `re.search(pattern, selector_value)` is truthy
`matches_any` | string | array[string] | Any regex matches

#### Numeric

Operator | Selector type | Value type | Semantics
---|---|---|---
`gt` | number | number | `>`
`gte` | number | number | `>=`
`lt` | number | number | `<`
`lte` | number | number | `<=`

**Regex engine:** Python `re` module. Patterns are compiled once at policy load time. Invalid regex is a validation error.

**Regex in YAML:** Use single-quoted strings to avoid escape issues. `'\b'` is a literal backslash-b. `"\b"` is a backspace character.

---

## 4. Action Block (`then`)

```yaml
then:
  effect: deny | warn       # required
  message: string            # required, min 1 char
  tags: [string, ...]        # optional, default []
  metadata: { ... }          # optional, arbitrary key-value
```

**Message templating:** Placeholders like `{args.path}`, `{tool.name}`, `{principal.user_id}` are expanded from the envelope at evaluation time. Missing placeholders are kept as-is (no crash). Each placeholder expansion is capped at 200 characters.

**Effect constraints by type:**

Type | Allowed effects
---|---
`pre` | `deny` only
`post` | `warn` only
`session` | `deny` only

---

## 5. Compilation Model

YAML contracts compile to the **same runtime objects** as Python contracts. No new runtime path.

### Pre → `@precondition`

```python
# This YAML:
#   id: block-reads
#   type: pre
#   tool: read_file
#   when:
#     args.path: { contains: ".env" }
#   then: { effect: deny, message: "..." }

# Compiles to equivalent of:
@precondition("read_file")
def block_reads(envelope: ToolEnvelope) -> Verdict:
    path = envelope.args.get("path")
    if path is None:
        return Verdict.pass_()
    if ".env" in path:
        return Verdict.fail("Sensitive file '...' blocked.")
    return Verdict.pass_()
```

### Post → `@postcondition`

```python
# Compiles to:
@postcondition("*")
def pii_in_output(envelope: ToolEnvelope, response) -> Verdict:
    text = str(response)
    if re.search(r'\b\d{3}-\d{2}-\d{4}\b', text):
        return Verdict.fail("PII detected...")
    return Verdict.pass_()
```

### Session → `OperationLimits`

```python
# Session contracts compile to OperationLimits overrides:
# limits.max_tool_calls = 25
# limits.max_attempts = 60
# limits.max_calls_per_tool = {"send_slack_message": 10}
# Custom message replaces the default pipeline message.
```

---

## 6. Error Handling (hardcoded, not configurable)

| Scenario | Behavior |
|---|---|
| YAML parse error | `callguard validate` rejects. `from_yaml()` raises `CallGuardConfigError`. |
| Invalid regex in `matches`/`matches_any` | Validation error at load time. |
| Rule evaluation throws (unexpected error) | Rule yields `deny` (pre/session) or `warn` (post). Audit event emitted with `policy_error: true`. Other rules continue evaluating. |
| Selector references missing field | Leaf evaluates to `false`. Not an error. |
| Type mismatch (e.g., `gt` on a string) | Rule yields `deny`/`warn` + `policy_error: true`. |
| Duplicate `id` in bundle | Validation error at load time. |

---

## 7. Principal Model (v1 additions)

```python
@dataclass(frozen=True)
class Principal:
    user_id: str | None = None
    service_id: str | None = None
    org_id: str | None = None
    # v1 additions:
    role: str | None = None
    ticket_ref: str | None = None
    claims: dict[str, Any] = field(default_factory=dict)
```

Adapters populate Principal from framework-specific context. If not provided, all `principal.*` selectors evaluate to `false` (missing field).

---

## 8. Audit Integration

Every contract evaluation stamps these fields on `AuditEvent`:

Field | Source
---|---
`policy_version` | SHA256 hash of bundle YAML bytes
`decision_name` | Contract `id`
`decision_source` | `"yaml_precondition"`, `"yaml_postcondition"`, `"yaml_session"`
`contracts_evaluated[].tags` | From `then.tags`
`policy_error` | `true` if rule evaluation threw

OTel span attributes:
- `callguard.policy_version`
- `callguard.policy_error` (if true)

---

## 9. Complete Example

```yaml
apiVersion: callguard/v1
kind: ContractBundle

metadata:
  name: devops-agent
  description: "Governance for CI/CD and infrastructure agents."

defaults:
  mode: enforce

contracts:
  # --- File safety ---
  - id: block-sensitive-reads
    type: pre
    tool: read_file
    when:
      args.path:
        contains_any: [".env", ".secret", "kubeconfig", "credentials", ".pem", "id_rsa"]
    then:
      effect: deny
      message: "Sensitive file '{args.path}' blocked. Skip and continue."
      tags: [secrets, dlp]

  # --- Bash safety ---
  - id: block-destructive-bash
    type: pre
    tool: bash
    when:
      any:
        - args.command: { matches: '\brm\s+(-rf?|--recursive)\b' }
        - args.command: { matches: '\bmkfs\b' }
        - args.command: { matches: '\bdd\s+' }
        - args.command: { contains: '> /dev/' }
    then:
      effect: deny
      message: "Destructive command blocked: '{args.command}'. Use a safer alternative."
      tags: [destructive, safety]

  # --- Production gate ---
  - id: prod-deploy-requires-senior
    type: pre
    tool: deploy_service
    when:
      all:
        - environment: { equals: production }
        - principal.role: { not_in: [senior_engineer, sre, admin] }
    then:
      effect: deny
      message: "Production deploys require senior role (sre/admin)."
      tags: [change-control, production]

  # --- Ticket required for prod changes ---
  - id: prod-requires-ticket
    type: pre
    tool: deploy_service
    when:
      all:
        - environment: { equals: production }
        - principal.ticket_ref: { exists: false }
    then:
      effect: deny
      message: "Production changes require a ticket reference."
      tags: [change-control, compliance]

  # --- PII detection ---
  - id: pii-in-output
    type: post
    tool: "*"
    when:
      output.text:
        matches_any:
          - '\b\d{3}-\d{2}-\d{4}\b'
          - '\b[A-Z]{2}\d{2}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\s?\d{0,2}\b'
    then:
      effect: warn
      message: "PII pattern detected in output. Redact before using."
      tags: [pii, compliance]

  # --- Observe mode: shadow-test new rule ---
  - id: experimental-api-rate-check
    type: pre
    mode: observe
    tool: call_api
    when:
      args.endpoint: { contains: "/v1/expensive" }
    then:
      effect: deny
      message: "Expensive API call detected (shadow mode)."
      tags: [cost, experimental]

  # --- Session limits ---
  - id: session-limits
    type: session
    limits:
      max_tool_calls: 50
      max_attempts: 120
      max_calls_per_tool:
        deploy_service: 3
        send_notification: 10
    then:
      effect: deny
      message: "Session limit reached. Summarize progress and stop."
      tags: [rate-limit]
```

---

## 10. What's NOT in v1 (deferred)

Feature | Reason | Target
---|---|---
`include` / composition | Debugging complexity; need user feedback on organization patterns | v1.1
Budget tracking (`max_cost_usd`) | Requires cost model not yet in codebase | v1.1
`principal.roles` (multi-role) | Changes operator semantics; `role: str` + `claims` sufficient for now | v1.1
Arbitrary session `when` conditions | Risk of YAML becoming a programming language | v1.1
`output` typing beyond `.text` | Need framework-specific response parsing | v1.1
Case-insensitive operators (`*_ci`) | No demand signal yet | v1.1
Signed/tamper-proof bundles | Important for compliance, not adoption-blocking | v1.2
