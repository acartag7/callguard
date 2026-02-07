# Data Protection Patterns

Data protection contracts prevent sensitive information from leaking through agent tool calls. They cover two sides: blocking access to sensitive files (preconditions) and scanning tool output for sensitive patterns (postconditions).

---

## PII Detection in Tool Output

Scan tool output for personally identifiable information using regex patterns. This is a postcondition because it inspects the result after the tool has run.

**When to use:** Your agent calls tools that return data from databases, APIs, or files that may contain personal data. You want an audit trail of PII exposure and a warning to the agent to redact before proceeding.

```yaml
apiVersion: edictum/v1
kind: ContractBundle

metadata:
  name: pii-detection

defaults:
  mode: enforce

contracts:
  - id: pii-in-output
    type: post
    tool: "*"
    when:
      output.text:
        matches_any:
          - '\\b\\d{3}-\\d{2}-\\d{4}\\b'
          - '\\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\\.[A-Z|a-z]{2,}\\b'
          - '\\b\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}[\\s-]?\\d{4}\\b'
          - '\\b\\d{3}[-.]?\\d{3}[-.]?\\d{4}\\b'
    then:
      effect: warn
      message: "PII pattern detected in output. Redact before using in summaries or responses."
      tags: [pii, compliance]
```

The patterns above detect:

| Pattern | Regex | Example Match |
|---|---|---|
| US SSN | `\b\d{3}-\d{2}-\d{4}\b` | 123-45-6789 |
| Email address | `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z\|a-z]{2,}\b` | user@example.com |
| Credit card | `\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b` | 4111-1111-1111-1111 |
| Phone number | `\b\d{3}[-.]?\d{3}[-.]?\d{4}\b` | 555-867-5309 |

**Gotchas:**
- Postconditions cannot undo the tool call. The data has already been returned. The warning tells the agent to redact, but the data is in the conversation context.
- Regex-based PII detection is a baseline. Production deployments should use ML-based PII scanners (Presidio, Phileas, etc.) behind the same postcondition contract interface.
- `matches_any` short-circuits on the first match. Order patterns from most common to least common for performance.
- The phone number regex will match some non-phone patterns like version numbers (e.g., `123.456.7890`). Tune patterns based on your data.

---

## Secret Scanning in Output

Detect credentials, tokens, and private keys in tool output. Even if a precondition allowed the read, the output may contain secrets that should not enter the conversation.

**When to use:** Defense in depth. Your agent reads files, calls APIs, or queries databases. Even if the input was allowed, the output may contain secrets leaked into logs, configs, or error messages.

```yaml
apiVersion: edictum/v1
kind: ContractBundle

metadata:
  name: secret-scanning

defaults:
  mode: enforce

contracts:
  - id: secrets-in-output
    type: post
    tool: "*"
    when:
      output.text:
        matches_any:
          - 'AKIA[0-9A-Z]{16}'
          - 'eyJ[A-Za-z0-9_-]+\\.eyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+'
          - '-----BEGIN (RSA |EC )?PRIVATE KEY-----'
    then:
      effect: warn
      message: "Secret detected in output. Do not reference, log, or output this value."
      tags: [secrets, dlp]
      metadata:
        severity: critical
```

The patterns above detect:

| Pattern | Regex | Example Match |
|---|---|---|
| AWS Access Key | `AKIA[0-9A-Z]{16}` | AKIAIOSFODNN7EXAMPLE |
| JWT Token | `eyJ...` (three dot-separated base64 segments) | eyJhbGciOiJ... |
| Private Key | PEM header format | -----BEGIN RSA PRIVATE KEY----- |

**Gotchas:**
- The AWS key pattern only matches access key IDs (starting with `AKIA`). It does not detect secret access keys, which are harder to distinguish from random strings. Add a separate pattern for `aws_secret_access_key\s*[:=]\s*\S+` if needed.
- JWT patterns match the structure but do not validate the token. Expired or invalid JWTs still trigger the warning, which is the desired behavior.

---

## Sensitive File Blocking

Block reads of files that commonly contain secrets, credentials, or private keys. This is a precondition -- it runs before the tool executes, so no data is exposed.

**When to use:** Your agent has access to `read_file` and you want to prevent it from reading files that could expose secrets, even accidentally.

```yaml
apiVersion: edictum/v1
kind: ContractBundle

metadata:
  name: sensitive-file-blocking

defaults:
  mode: enforce

contracts:
  - id: block-secret-files
    type: pre
    tool: read_file
    when:
      args.path:
        contains_any:
          - ".env"
          - ".secret"
          - "credentials"
          - ".pem"
          - "id_rsa"
          - ".key"
          - "kubeconfig"
    then:
      effect: deny
      message: "Reading sensitive file '{args.path}' is blocked. Skip and continue with non-sensitive files."
      tags: [secrets, dlp]

  - id: block-config-with-secrets
    type: pre
    tool: read_file
    when:
      any:
        - args.path: { ends_with: ".tfvars" }
        - args.path: { ends_with: ".npmrc" }
        - args.path: { ends_with: ".pypirc" }
        - args.path: { ends_with: ".netrc" }
    then:
      effect: deny
      message: "Config file '{args.path}' may contain credentials. Access blocked."
      tags: [secrets, dlp]
```

**Gotchas:**
- `contains_any` is a substring match. A path like `/reports/environment.log` would match on `.env`. Use `ends_with` or `matches` with word boundaries for more precise matching.
- This pattern only protects `read_file`. If your agent has a `bash` tool, it could read the same files with `cat`. Add corresponding rules for all file-reading tools.

---

## Output Size Monitoring

Warn when tool output is unusually large, which can waste context window tokens and cause the agent to lose track of its task.

**When to use:** Your agent reads files or queries databases where unbounded results are possible. Large outputs dilute the agent's focus and increase token costs.

```yaml
apiVersion: edictum/v1
kind: ContractBundle

metadata:
  name: output-monitoring

defaults:
  mode: enforce

contracts:
  - id: large-output-warning
    type: post
    tool: "*"
    when:
      output.text:
        matches: '.{50000,}'
    then:
      effect: warn
      message: "Tool output is very large. Use pagination, head/tail, or more specific filters."
      tags: [performance, output-size]
```

**Gotchas:**
- The `.{50000,}` regex matches any string with 50,000 or more characters. This is a rough proxy for output size. Adjust the threshold based on your context window budget.
- Large regex matches can be slow. If performance is a concern, consider implementing output size monitoring as a Python postcondition instead, where you can use `len()` directly.
