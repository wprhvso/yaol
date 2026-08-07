# yaol

Yet another observability library. Wires OpenTelemetry traces, metrics and logs
plus structlog and Pyroscope profiling from a single config object.

## Usage

```python
from yaol import ObservabilityConfig, setup, shutdown, instrument_asyncpg

config = ObservabilityConfig(
    service_name="bot",
    service_version="0.1.7",
    environment="prod",
    otlp_endpoint="http://172.17.0.1:4317",
    logger_levels={"sqlalchemy.engine": "WARNING"},
)

setup(config)
instrument_asyncpg()
...
shutdown()
```

`from_env` builds the same object from environment variables:
`ENV`, `OTEL_EXPORTER_OTLP_ENDPOINT`, `LOG_LEVEL`, `YAOL_JSON_LOGS`,
`YAOL_EXPORT_LOGS`, `YAOL_EXPORT_METRICS`, `YAOL_METRIC_INTERVAL_MILLIS`,
`YAOL_PROFILING_ENABLED`, `PYROSCOPE_ADDRESS`, `PYROSCOPE_SAMPLE_RATE`.

## Signals

- Traces — OTLP gRPC, `BatchSpanProcessor`.
- Metrics — OTLP gRPC, `PeriodicExportingMetricReader`.
- Logs — OTLP gRPC alongside the stdout handler; both are attached to the root logger.
- Profiles — Pyroscope push, off by default.

`shutdown()` flushes every provider, which the previous ad-hoc setup did not do.
