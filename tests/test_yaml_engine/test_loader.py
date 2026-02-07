"""Tests for the YAML bundle loader."""

from __future__ import annotations

from pathlib import Path

import pytest

from callguard import CallGuardConfigError
from callguard.yaml_engine.loader import BundleHash, load_bundle

FIXTURES = Path(__file__).parent / "fixtures"


class TestLoadBundle:
    """Tests for load_bundle()."""

    def test_valid_bundle_loads(self):
        data, bundle_hash = load_bundle(FIXTURES / "valid_bundle.yaml")
        assert data["apiVersion"] == "callguard/v1"
        assert data["kind"] == "ContractBundle"
        assert data["metadata"]["name"] == "test-bundle"
        assert len(data["contracts"]) == 3

    def test_valid_bundle_returns_hash(self):
        _, bundle_hash = load_bundle(FIXTURES / "valid_bundle.yaml")
        assert isinstance(bundle_hash, BundleHash)
        assert len(bundle_hash.hex) == 64  # SHA256 hex digest

    def test_hash_is_deterministic(self):
        _, h1 = load_bundle(FIXTURES / "valid_bundle.yaml")
        _, h2 = load_bundle(FIXTURES / "valid_bundle.yaml")
        assert h1.hex == h2.hex

    def test_hash_str_representation(self):
        _, bundle_hash = load_bundle(FIXTURES / "valid_bundle.yaml")
        assert str(bundle_hash) == bundle_hash.hex

    def test_contract_types_parsed(self):
        data, _ = load_bundle(FIXTURES / "valid_bundle.yaml")
        types = [c["type"] for c in data["contracts"]]
        assert types == ["pre", "post", "session"]

    def test_pre_contract_structure(self):
        data, _ = load_bundle(FIXTURES / "valid_bundle.yaml")
        pre = data["contracts"][0]
        assert pre["id"] == "block-sensitive-reads"
        assert pre["type"] == "pre"
        assert pre["tool"] == "read_file"
        assert "args.path" in pre["when"]
        assert pre["then"]["effect"] == "deny"
        assert pre["then"]["tags"] == ["secrets", "dlp"]

    def test_session_contract_structure(self):
        data, _ = load_bundle(FIXTURES / "valid_bundle.yaml")
        session = data["contracts"][2]
        assert session["id"] == "session-limits"
        assert session["type"] == "session"
        assert session["limits"]["max_tool_calls"] == 50
        assert session["limits"]["max_attempts"] == 120


class TestSchemaValidation:
    """Tests for JSON Schema validation failures."""

    def test_missing_apiversion(self):
        with pytest.raises(CallGuardConfigError, match="Schema validation failed"):
            load_bundle(FIXTURES / "invalid_missing_apiversion.yaml")

    def test_bad_effect_on_post(self):
        with pytest.raises(CallGuardConfigError, match="Schema validation failed"):
            load_bundle(FIXTURES / "invalid_bad_effect.yaml")

    def test_empty_contracts(self):
        with pytest.raises(CallGuardConfigError, match="Schema validation failed"):
            load_bundle(FIXTURES / "invalid_empty_contracts.yaml")

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            load_bundle(FIXTURES / "nonexistent.yaml")


class TestDuplicateIdValidation:
    """Tests for duplicate contract ID detection."""

    def test_duplicate_ids_rejected(self):
        with pytest.raises(CallGuardConfigError, match="Duplicate contract id"):
            load_bundle(FIXTURES / "invalid_duplicate_ids.yaml")


class TestRegexValidation:
    """Tests for regex pattern validation at load time."""

    def test_invalid_regex_rejected(self):
        with pytest.raises(CallGuardConfigError, match="Invalid regex pattern"):
            load_bundle(FIXTURES / "invalid_bad_regex.yaml")

    def test_valid_regex_accepted(self):
        data, _ = load_bundle(FIXTURES / "valid_bundle.yaml")
        # The valid bundle has matches_any with regex — should pass
        post = data["contracts"][1]
        assert "matches_any" in post["when"]["output.text"]


class TestYamlParseErrors:
    """Tests for YAML parsing error handling."""

    def test_invalid_yaml_syntax(self, tmp_path):
        bad = tmp_path / "bad.yaml"
        bad.write_text("{\n  invalid: yaml: syntax:\n}")
        with pytest.raises(CallGuardConfigError, match="YAML parse error"):
            load_bundle(bad)

    def test_non_mapping_yaml(self, tmp_path):
        scalar = tmp_path / "scalar.yaml"
        scalar.write_text("just a string")
        with pytest.raises(CallGuardConfigError, match="YAML document must be a mapping"):
            load_bundle(scalar)
