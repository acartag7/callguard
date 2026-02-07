# Access Control Patterns

Access control contracts determine **who** can use **which tools** in **which environments**. They are preconditions -- they evaluate before the tool runs, and denial is free because nothing has happened yet.

---

## Role-Based Access

The most common pattern. Use `principal.role` with `in` or `not_in` to restrict tools to specific roles.

**When to use:** You have a fixed set of roles (admin, analyst, viewer) and want to gate dangerous tools behind privileged roles.

```yaml
apiVersion: edictum/v1
kind: ContractBundle

metadata:
  name: role-based-access

defaults:
  mode: enforce

contracts:
  - id: admin-only-deploy
    type: pre
    tool: deploy_service
    when:
      principal.role:
        not_in: [admin, sre]
    then:
      effect: deny
      message: "Only admin and sre roles can deploy. Your role: {principal.role}."
      tags: [access-control, production]

  - id: viewer-read-only
    type: pre
    tool: run_command
    when:
      principal.role:
        equals: viewer
    then:
      effect: deny
      message: "Viewer role cannot execute commands. Request analyst or admin access."
      tags: [access-control]
```

**Gotchas:**
- If no principal is attached to the call, `principal.role` is missing. Missing fields cause the leaf to evaluate to `false`, so the rule does **not** fire. This means unauthenticated calls slip through. Add a separate `principal.role: { exists: false }` contract to catch missing principals.
- The `not_in` operator checks whether the value is absent from the list. `not_in: [admin, sre]` blocks everyone except admin and sre -- including missing roles (which evaluate to `false`, not firing the rule). Pair with an `exists` check for defense in depth.

---

## Environment-Aware Contracts

Restrict tools based on the deployment environment. The `environment` selector resolves from the environment parameter set when you construct the `Edictum` instance.

**When to use:** Different environments have different risk profiles. Production needs stricter controls than staging or development.

```yaml
apiVersion: edictum/v1
kind: ContractBundle

metadata:
  name: environment-gates

defaults:
  mode: enforce

contracts:
  - id: prod-requires-admin
    type: pre
    tool: run_command
    when:
      all:
        - environment: { equals: production }
        - principal.role: { not_in: [admin, sre] }
    then:
      effect: deny
      message: "Production commands require admin or sre role."
      tags: [access-control, production]

  - id: staging-no-write
    type: pre
    tool: query_database
    when:
      all:
        - environment: { equals: staging }
        - args.query: { matches: '\\b(INSERT|UPDATE|DELETE)\\b' }
    then:
      effect: deny
      message: "Write queries are blocked in staging. Use read-only queries."
      tags: [access-control, staging]
```

**Gotchas:**
- The `environment` value is set at `Edictum` construction time, not per-call. If your application uses a single `Edictum` instance across environments, environment-based rules will always see the same value.
- Regex patterns in `matches` use single-quoted YAML strings. Double-quoted strings interpret `\b` as a backspace character instead of a regex word boundary.

---

## Attribute-Based Access

Use `principal.claims.<key>` to access custom attributes beyond the built-in fields. Claims are arbitrary key-value pairs attached to the principal.

**When to use:** Your authorization model goes beyond simple roles. You need to check department, clearance level, team membership, or other domain-specific attributes.

```yaml
apiVersion: edictum/v1
kind: ContractBundle

metadata:
  name: attribute-based-access

defaults:
  mode: enforce

contracts:
  - id: require-clearance-for-sensitive-data
    type: pre
    tool: query_database
    when:
      all:
        - args.table: { in: [audit_logs, access_records, user_sessions] }
        - principal.claims.clearance: { not_in: [high, critical] }
    then:
      effect: deny
      message: "Querying '{args.table}' requires high or critical clearance."
      tags: [access-control, sensitive-data]

  - id: department-restricted-tool
    type: pre
    tool: send_email
    when:
      principal.claims.department:
        not_in: [marketing, communications]
    then:
      effect: deny
      message: "Only marketing and communications can use send_email."
      tags: [access-control, department]
```

**Gotchas:**
- Claims are set by your application when constructing the `Principal` object. Edictum does not validate claims against an external identity provider.
- If a claim key is missing, the leaf evaluates to `false` and the rule does not fire. Use `principal.claims.<key>: { exists: false }` to explicitly require a claim be present.

---

## Role Escalation Prevention

Block actions that would change a user's own role or permissions. This prevents agents from self-promoting or modifying access controls.

**When to use:** Your agent has access to user management or configuration tools, and you want to prevent it from escalating privileges.

```yaml
apiVersion: edictum/v1
kind: ContractBundle

metadata:
  name: escalation-prevention

defaults:
  mode: enforce

contracts:
  - id: block-role-change
    type: pre
    tool: run_command
    when:
      any:
        - args.command: { contains: "role" }
        - args.command: { contains: "permission" }
        - args.command: { contains: "grant" }
    then:
      effect: deny
      message: "Commands that modify roles or permissions are blocked."
      tags: [access-control, escalation]

  - id: block-admin-config-writes
    type: pre
    tool: write_file
    when:
      args.path:
        contains_any: ["rbac", "permissions", "roles.yaml", "access-control"]
    then:
      effect: deny
      message: "Writing to access control configuration files is blocked."
      tags: [access-control, escalation]
```

**Gotchas:**
- The `contains` operator is a substring match, which can produce false positives. A command like `echo "user role in report"` would be caught. Use `matches` with word boundaries for more precise matching when needed.
- Escalation prevention is defense in depth. It should complement your application's own authorization layer, not replace it.
