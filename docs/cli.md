# CLI Reference

CallGuard ships a command-line interface for validating contract files, dry-running
tool calls, diffing policy versions, and replaying audit logs against updated contracts.

## Installation

```bash
pip install callguard[cli]
```

This pulls in [Click](https://click.palletsprojects.com/) and
[Rich](https://rich.readthedocs.io/) as additional dependencies. The `callguard`
command becomes available on your `PATH` via the entry point defined in `pyproject.toml`
(`callguard.cli.main:cli`).

---

## Commands

### `callguard validate`

Parse a YAML contract file, validate it against the CallGuard JSON Schema, compile
all regex patterns, check for unique contract IDs, and report any errors with line
numbers.

**Usage**

```
callguard validate <file.yaml>
```

**Options**

| Flag | Description |
|------|-------------|
| `--schema PATH` | Override the built-in JSON Schema file |
| `--strict` | Treat warnings as errors (non-zero exit code) |

**Example**

```
$ callguard validate contracts/production.yaml

  contracts/production.yaml

  Contracts ............. 12 loaded
  Preconditions ........ 8
  Postconditions ....... 2
  Session contracts .... 2
  Regex patterns ....... 5 compiled OK
  Unique IDs ........... 12/12

  OK  All checks passed.
```

When validation fails, errors include the YAML line number and a description of the
problem:

```
$ callguard validate contracts/broken.yaml

  contracts/broken.yaml

  ERROR line 14: Duplicate contract ID "no-secrets" (first defined at line 3)
  ERROR line 27: Invalid regex in match pattern: unterminated group at position 8
  ERROR line 31: Unknown side_effect value "dangerous" — expected one of: pure, read, write, irreversible

  FAIL  3 errors found.
```

Exit codes: `0` on success, `1` on validation errors, `2` on file-not-found or parse
failure.

---

### `callguard check`

Dry-run a single tool call envelope against your contracts. Builds a `ToolEnvelope`
from the provided tool name and arguments, evaluates all matching preconditions and
session contracts, and prints the verdict. No tool actually executes.

**Usage**

```
callguard check <file.yaml> --tool <name> --args '<json>'
```

**Options**

| Flag | Description |
|------|-------------|
| `--tool NAME` | Tool name to simulate (required) |
| `--args JSON` | Tool arguments as a JSON string (required) |
| `--principal JSON` | Principal context as a JSON string (optional) |
| `--env NAME` | Environment name, defaults to `production` |
| `--mode MODE` | `enforce` (default) or `observe` |

**Example -- allowed call**

```
$ callguard check contracts/production.yaml \
    --tool Read \
    --args '{"file_path": "/app/config.json"}'

  Tool:        Read
  Args:        {"file_path": "/app/config.json"}
  Side effect: read
  Principal:   (none)

  Contracts evaluated:
    no-secrets .............. PASS
    read-allowlist .......... PASS

  Verdict: ALLOWED
```

**Example -- denied call with principal**

```
$ callguard check contracts/production.yaml \
    --tool Bash \
    --args '{"command": "rm -rf /tmp/data"}' \
    --principal '{"role": "sre", "ticket_ref": "INC-4421"}'

  Tool:        Bash
  Args:        {"command": "rm -rf /tmp/data"}
  Side effect: irreversible
  Principal:   role=sre, ticket_ref=INC-4421

  Contracts evaluated:
    no-destructive-bash ..... FAIL
      "Destructive bash command blocked: rm -rf. Requires role=admin."

  Verdict: DENIED
    Source:  precondition
    Rule:    no-destructive-bash
    Reason:  Destructive bash command blocked: rm -rf. Requires role=admin.
```

---

### `callguard diff`

Compare two YAML contract files and report which contract IDs were added, removed,
or changed. Useful for code review and change management workflows.

**Usage**

```
callguard diff <old.yaml> <new.yaml>
```

**Options**

| Flag | Description |
|------|-------------|
| `--format FORMAT` | Output format: `text` (default), `json` |
| `--quiet` | Only print the summary counts |

**Example**

```
$ callguard diff contracts/v1.yaml contracts/v2.yaml

  Comparing contracts/v1.yaml → contracts/v2.yaml

  Added (2):
    + require-ticket-ref     precondition for Bash
    + max-writes-per-session  session_contract

  Removed (1):
    - legacy-read-block      precondition for Read

  Changed (1):
    ~ no-secrets             match pattern updated
                             old: "/\\.env$"
                             new: "/\\.env|\\.secret$"

  Summary: 2 added, 1 removed, 1 changed
  Policy hash: old=a3f1c9... new=8b2d4e...
```

Exit codes: `0` if identical, `1` if differences found, `2` on file errors.

---

### `callguard replay`

Replay an audit log (JSONL) against a contract file and report what would change.
Each event in the audit log is re-evaluated as if the new contracts were in effect at
the time. This answers the question: "If I deploy these contracts, which past calls
would have been treated differently?"

**Usage**

```
callguard replay --contracts <file.yaml> --audit-log <events.jsonl>
```

**Options**

| Flag | Description |
|------|-------------|
| `--contracts PATH` | YAML contract file to evaluate against (required) |
| `--audit-log PATH` | JSONL audit log file to replay (required) |
| `--format FORMAT` | Output format: `text` (default), `json` |
| `--only-changes` | Only show events whose verdict would differ |

**Example**

```
$ callguard replay \
    --contracts contracts/v2.yaml \
    --audit-log /var/log/callguard/2025-01-15.jsonl \
    --only-changes

  Replaying 1,247 events against contracts/v2.yaml ...

  Event 42   call_id=a1b2c3  Bash {"command": "cat /etc/passwd"}
    Was:     ALLOWED
    Now:     DENIED (no-sensitive-reads)
    Reason:  Access to sensitive path blocked: /etc/passwd

  Event 891  call_id=d4e5f6  Write {"file_path": "/app/.env.bak"}
    Was:     ALLOWED
    Now:     DENIED (no-secrets)
    Reason:  Write to sensitive path blocked: .env

  Summary:
    Total events ......... 1,247
    Unchanged ............ 1,245
    Would change ......... 2
      ALLOWED → DENIED ... 2
      DENIED → ALLOWED ... 0
```

---

## Combining with CI/CD

All commands return structured exit codes suitable for pipeline gating:

```yaml
# GitHub Actions example
- name: Validate contracts
  run: callguard validate contracts/production.yaml --strict

- name: Diff against main
  run: |
    git show main:contracts/production.yaml > /tmp/old.yaml
    callguard diff /tmp/old.yaml contracts/production.yaml

- name: Replay last week's audit log
  run: |
    callguard replay \
      --contracts contracts/production.yaml \
      --audit-log audit/last-week.jsonl \
      --only-changes --format json > replay-report.json
```
