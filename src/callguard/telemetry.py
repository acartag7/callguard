"""OpenTelemetry span and metric helpers.

Provides governance-specific tracing and metrics. Gracefully degrades
to no-ops if OpenTelemetry is not installed.
"""

from __future__ import annotations

from typing import Any

try:
    from opentelemetry import trace

    _tracer = trace.get_tracer("callguard")
    _HAS_OTEL = True
except ImportError:
    _HAS_OTEL = False
    _tracer = None


def start_governance_span(name: str, attributes: dict[str, Any] | None = None) -> Any:
    """Start an OTel span for a governance operation.

    Returns a context manager. If OTel is not installed, returns a no-op.
    """
    if _HAS_OTEL and _tracer is not None:
        return _tracer.start_as_current_span(name, attributes=attributes)
    return _NoOpSpan()


class _NoOpSpan:
    """No-op context manager used when OTel is not available."""

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        pass
