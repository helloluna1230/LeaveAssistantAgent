"""Observability: OpenTelemetry + Application Insights wiring and PII redaction.

Spans emitted by the agent/tool layer flow to Application Insights when
APPLICATIONINSIGHTS_CONNECTION_STRING is set. Redaction helpers keep tokens,
keys, and raw employee ids out of traces and logs.
"""

from __future__ import annotations

import logging
import re
import time
from contextlib import contextmanager

logger = logging.getLogger("leave_assistant.observability")

_TOKEN_RE = re.compile(r"(?i)(bearer\s+)[A-Za-z0-9._\-]+")
_EMP_RE = re.compile(r"\b([EM])(\d{2})(\d+)\b")


def setup_observability(config) -> None:
    """Best-effort telemetry setup; never fails the agent if unavailable."""
    if not config.enable_instrumentation:
        return
    if not config.app_insights_conn:
        logger.info("APPLICATIONINSIGHTS_CONNECTION_STRING not set; telemetry export disabled.")
        return
    try:
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            connection_string=config.app_insights_conn,
            service_name=config.agent_name,
        )
        logger.info("Application Insights telemetry configured for %s.", config.agent_name)
    except Exception as exc:  # noqa: BLE001 - telemetry must never break the agent
        logger.warning("Telemetry setup skipped: %s", exc)


def get_tracer(name: str = "leave_assistant"):
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except Exception:  # noqa: BLE001
        return _NoopTracer()


def mask_user(employee_id: str | None) -> str:
    if not employee_id:
        return "anon"
    return employee_id[:2] + "***" if len(employee_id) > 2 else "***"


def redact(value) -> str:
    """Redact bearer tokens and partially mask employee ids in free text."""
    text = value if isinstance(value, str) else str(value)
    text = _TOKEN_RE.sub(r"\1***", text)
    text = _EMP_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}***", text)
    return text


def current_trace_id() -> str | None:
    """Hex trace id of the active span, or None when tracing is disabled."""
    try:
        from opentelemetry import trace

        ctx = trace.get_current_span().get_span_context()
        if getattr(ctx, "trace_id", 0):
            return format(ctx.trace_id, "032x")
    except Exception:  # noqa: BLE001
        return None
    return None


@contextmanager
def traced(name: str, *, user_id: str | None = None, **attrs):
    """Start a span with standard, pre-redacted attributes and record latency/errors."""
    tracer = get_tracer()
    start = time.perf_counter()
    with tracer.start_as_current_span(name) as span:
        if user_id is not None:
            span.set_attribute("user.masked_id", mask_user(user_id))
        for key, value in attrs.items():
            if value is not None:
                span.set_attribute(key, redact(value) if isinstance(value, str) else value)
        try:
            yield span
        except Exception as exc:  # noqa: BLE001
            span.set_attribute("error.type", type(exc).__name__)
            raise
        finally:
            span.set_attribute("latency.ms", round((time.perf_counter() - start) * 1000, 2))


class _NoopSpan:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def set_attribute(self, *args, **kwargs):
        pass


class _NoopTracer:
    def start_as_current_span(self, *args, **kwargs):
        return _NoopSpan()
