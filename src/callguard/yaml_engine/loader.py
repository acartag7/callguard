"""YAML Bundle Loader — parse, validate against JSON Schema, compute bundle hash."""

from __future__ import annotations

import hashlib
import importlib.resources as _resources
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import jsonschema
    import yaml
except ImportError as _exc:
    raise ImportError(
        "The YAML engine requires pyyaml and jsonschema. Install them with: pip install callguard[yaml]"
    ) from _exc

MAX_BUNDLE_SIZE = 1_048_576  # 1 MB

# Lazy-loaded schema singleton
_schema_cache: dict | None = None


def _get_schema() -> dict:
    """Load and cache the JSON Schema for validation."""
    global _schema_cache  # noqa: PLW0603
    if _schema_cache is None:
        import json

        schema_text = (
            _resources.files("callguard.yaml_engine").joinpath("callguard-v1.schema.json").read_text(encoding="utf-8")
        )
        _schema_cache = json.loads(schema_text)
    return _schema_cache


@dataclass(frozen=True)
class BundleHash:
    """SHA256 hash of raw YAML bytes, used as policy_version."""

    hex: str

    def __str__(self) -> str:
        return self.hex


def _compute_hash(raw_bytes: bytes) -> BundleHash:
    """Compute SHA256 hash of raw YAML bytes."""
    return BundleHash(hex=hashlib.sha256(raw_bytes).hexdigest())


def _validate_schema(data: dict) -> None:
    """Validate parsed YAML against the CallGuard JSON Schema."""
    from callguard import CallGuardConfigError

    schema = _get_schema()
    try:
        jsonschema.validate(instance=data, schema=schema)
    except jsonschema.ValidationError as e:
        raise CallGuardConfigError(f"Schema validation failed: {e.message}") from e


def _validate_unique_ids(data: dict) -> None:
    """Ensure all contract IDs are unique within the bundle."""
    from callguard import CallGuardConfigError

    ids: set[str] = set()
    for contract in data.get("contracts", []):
        contract_id = contract.get("id")
        if contract_id in ids:
            raise CallGuardConfigError(f"Duplicate contract id: '{contract_id}'")
        ids.add(contract_id)


def _validate_regexes(data: dict) -> None:
    """Compile all regex patterns at load time to catch invalid patterns early."""

    for contract in data.get("contracts", []):
        when = contract.get("when")
        if when:
            _validate_expression_regexes(when)


def _validate_expression_regexes(expr: dict | Any) -> None:
    """Recursively validate regex patterns in expressions."""

    if not isinstance(expr, dict):
        return

    # Boolean nodes
    if "all" in expr:
        for sub in expr["all"]:
            _validate_expression_regexes(sub)
        return
    if "any" in expr:
        for sub in expr["any"]:
            _validate_expression_regexes(sub)
        return
    if "not" in expr:
        _validate_expression_regexes(expr["not"])
        return

    # Leaf node: selector -> operator
    for _selector, operator in expr.items():
        if not isinstance(operator, dict):
            continue
        if "matches" in operator:
            _try_compile_regex(operator["matches"])
        if "matches_any" in operator:
            for pattern in operator["matches_any"]:
                _try_compile_regex(pattern)


def _validate_pre_selectors(data: dict) -> None:
    """Reject output.text selectors in type: pre contracts (spec violation)."""
    from callguard import CallGuardConfigError

    for contract in data.get("contracts", []):
        if contract.get("type") != "pre":
            continue
        when = contract.get("when")
        if when and _expression_has_selector(when, "output.text"):
            raise CallGuardConfigError(
                f"Contract '{contract.get('id', '?')}': output.text selector is not available in type: pre contracts"
            )


def _expression_has_selector(expr: dict | Any, target: str) -> bool:
    """Check if an expression tree contains a specific selector."""
    if not isinstance(expr, dict):
        return False
    if "all" in expr:
        return any(_expression_has_selector(sub, target) for sub in expr["all"])
    if "any" in expr:
        return any(_expression_has_selector(sub, target) for sub in expr["any"])
    if "not" in expr:
        return _expression_has_selector(expr["not"], target)
    # Leaf node: check selector keys
    return target in expr


def _try_compile_regex(pattern: str) -> None:
    """Attempt to compile a regex pattern, raising CallGuardConfigError on failure."""
    from callguard import CallGuardConfigError

    try:
        re.compile(pattern)
    except re.error as e:
        raise CallGuardConfigError(f"Invalid regex pattern '{pattern}': {e}") from e


def load_bundle(source: str | Path) -> tuple[dict, BundleHash]:
    """Load and validate a YAML contract bundle.

    Args:
        source: Path to a YAML file.

    Returns:
        Tuple of (parsed bundle dict, bundle hash).

    Raises:
        CallGuardConfigError: If the YAML is invalid, fails schema validation,
            has duplicate contract IDs, or contains invalid regex patterns.
        FileNotFoundError: If the file does not exist.
    """
    from callguard import CallGuardConfigError

    path = Path(source)

    file_size = path.stat().st_size
    if file_size > MAX_BUNDLE_SIZE:
        raise CallGuardConfigError(f"Bundle file too large ({file_size} bytes, max {MAX_BUNDLE_SIZE})")

    raw_bytes = path.read_bytes()
    bundle_hash = _compute_hash(raw_bytes)

    try:
        data = yaml.safe_load(raw_bytes)
    except yaml.YAMLError as e:
        raise CallGuardConfigError(f"YAML parse error: {e}") from e

    if not isinstance(data, dict):
        raise CallGuardConfigError("YAML document must be a mapping")

    _validate_schema(data)
    _validate_unique_ids(data)
    _validate_regexes(data)
    _validate_pre_selectors(data)

    return data, bundle_hash
