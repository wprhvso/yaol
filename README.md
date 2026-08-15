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
`YAOL_PROFILING_ENABLED`, `PYROSCOPE_ADDRESS`, `PYROSCOPE_SAMPLE_RATE`,
`YAOL_TRACE_SAMPLE_RATIO`, `YAOL_SPAN_QUEUE_SIZE`,
`YAOL_SPAN_SCHEDULE_DELAY_MILLIS`, `YAOL_SPAN_EXPORT_BATCH_SIZE`.

## Keeping a trace whole

A trace is only useful if it survives the places where work is handed off.
Three of those places need help.

**Errors that are handled.** A span that catches an exception ends with an OK
status, so the backend shows a green trace for a failed request. `SHARED_PROCESSORS`
mirrors every `log.error`/`log.exception` onto the active span as an exception
event plus an ERROR status, which covers handled errors without touching the
call sites. Use `record_exception` or `fail` where there is no log line:

```python
from yaol import fail, record_exception, span

with span("chat.pipeline"):
    try:
        await run()
    except Exception as error:
        record_exception(error)  # span is now ERROR, with a stack trace
        await tell_the_user(error)
```

`span()` also records cancellation, which the SDK deliberately ignores — work
killed by a timeout or a shutdown would otherwise export as a healthy span.

**Deferred work.** `asyncio` copies the caller's context into every task, so a
task created inside a span adopts it permanently. Long-lived workers must start
clean, and deferred work must resume the context it was scheduled from:

```python
from yaol import capture, spawn

worker = spawn(run_forever())              # clean context, its own traces
later = spawn(handle(batch), context=ctx)  # continues the captured trace
```

`capture()` takes the snapshot at scheduling time, `attached()` resumes it, and
`detached()` drops the ambient trace. When several traces converge on one unit
of work, parent it to the first and pass the rest as `links(contexts)`.

**Service boundaries.** Instrumented clients propagate the trace themselves —
`instrument_httpx()` covers SDKs that build their own client, the OpenAI SDK
among them — and `instrument_fastapi(app)` continues the caller's trace on the
receiving side. `inject_headers`/`extract_context` cover hops nothing
instruments.

## Signals

- Traces — OTLP gRPC, `BatchSpanProcessor`.
- Metrics — OTLP gRPC, `PeriodicExportingMetricReader`.
- Logs — OTLP gRPC alongside the stdout handler; both are attached to the root logger.
- Profiles — Pyroscope push, off by default.

`shutdown()` flushes every provider, which the previous ad-hoc setup did not do.
