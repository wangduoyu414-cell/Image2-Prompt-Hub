"""Externally configured JSON logging, Sentry, and OpenTelemetry."""

from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
import sentry_sdk


_LOCK = threading.Lock()
_CONFIGURED = False
_LOGGING_CONFIGURED = False


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "severity": record.levelname.lower(),
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, sort_keys=True)


def _configure_json_logging() -> None:
    global _LOGGING_CONFIGURED
    with _LOCK:
        if _LOGGING_CONFIGURED:
            return
        formatter = JsonLogFormatter()
        configured = False
        for logger_name in ("", "uvicorn", "uvicorn.error", "uvicorn.access", "dramatiq"):
            logger = logging.getLogger(logger_name)
            for handler in logger.handlers:
                handler.setFormatter(formatter)
                configured = True
        if not configured:
            handler = logging.StreamHandler()
            handler.setFormatter(formatter)
            logging.getLogger().addHandler(handler)
        _LOGGING_CONFIGURED = True


def configure_observability(service_name: str, *, app: FastAPI | None = None) -> None:
    global _CONFIGURED
    _configure_json_logging()
    dsn = os.environ.get("SENTRY_DSN", "").strip()
    if dsn:
        sentry_sdk.init(
            dsn=dsn,
            environment=os.environ.get("IMAGE2_ENVIRONMENT", "production"),
            release=os.environ.get("IMAGE2_RELEASE"),
            send_default_pii=False,
        )
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    console = os.environ.get("OTEL_CONSOLE_EXPORTER", "false").casefold() == "true"
    if endpoint or console:
        if endpoint:
            parsed = urlparse(endpoint)
            if parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username or parsed.password:
                raise ValueError("OTEL_EXPORTER_OTLP_ENDPOINT must be an absolute HTTP(S) URL without credentials")
        with _LOCK:
            if not _CONFIGURED:
                provider = TracerProvider(resource=Resource.create({"service.name": service_name}))
                exporter = OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces") if endpoint else ConsoleSpanExporter()
                provider.add_span_processor(BatchSpanProcessor(exporter))
                trace.set_tracer_provider(provider)
                _CONFIGURED = True
        if app is not None and _CONFIGURED and not getattr(app.state, "otel_instrumented", False):
            FastAPIInstrumentor.instrument_app(app)
            app.state.otel_instrumented = True
