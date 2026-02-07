"""Enterprise audit sinks for Edictum."""

from __future__ import annotations

from edictum.sinks.datadog import DatadogSink
from edictum.sinks.splunk import SplunkHECSink
from edictum.sinks.webhook import WebhookAuditSink

__all__ = [
    "DatadogSink",
    "SplunkHECSink",
    "WebhookAuditSink",
]
