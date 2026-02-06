"""YAML Contract Engine — parse, validate, and compile YAML contract bundles.

Requires optional dependencies: ``pip install callguard[yaml]``
"""

from __future__ import annotations

from callguard.yaml_engine.compiler import CompiledBundle
from callguard.yaml_engine.loader import BundleHash


def load_bundle(source: str) -> tuple[dict, BundleHash]:
    """Load and validate a YAML contract bundle. See :func:`loader.load_bundle`."""
    from callguard.yaml_engine.loader import load_bundle as _load

    return _load(source)


def compile_contracts(bundle: dict) -> CompiledBundle:
    """Compile a parsed bundle into contract objects. See :func:`compiler.compile_contracts`."""
    from callguard.yaml_engine.compiler import compile_contracts as _compile

    return _compile(bundle)


__all__ = [
    "BundleHash",
    "CompiledBundle",
    "compile_contracts",
    "load_bundle",
]
