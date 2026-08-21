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
`YAOL_EXPORT_TRACES`, `YAOL_EXPORT_LOGS`, `YAOL_EXPORT_METRICS`, `YAOL_METRIC_INTERVAL_MILLIS`,
`YAOL_PROFILING_ENABLED`, `PYROSCOPE_ADDRESS`, `PYROSCOPE_SAMPLE_RATE`,
`PYROSCOPE_ONCPU`, `PYROSCOPE_GIL_ONLY`, `PYROSCOPE_REPORT_PID`,
`PYROSCOPE_REPORT_THREAD_ID`, `PYROSCOPE_TAGS`,
`YAOL_TRACE_SAMPLE_RATIO`, `YAOL_SPAN_QUEUE_SIZE`,
`YAOL_SPAN_SCHEDULE_DELAY_MILLIS`, `YAOL_SPAN_EXPORT_BATCH_SIZE`.

`PYROSCOPE_TAGS` is a `key=value,key=value` list. Entries without `=` or with an
empty key are dropped rather than fatal, values may themselves contain `=`, and
the last duplicate wins.

## Kubernetes

Profiles need pod identity to be worth reading — with several replicas pushing
under one `application_name`, every flamegraph is a blend. Give the agent the
pod name through the downward API:

```yaml
env:
  - name: POD_NAME
    valueFrom:
      fieldRef:
        fieldPath: metadata.name
  - name: PYROSCOPE_TAGS
    value: "pod=$(POD_NAME)"
```

Resource attributes arrive the same way, but `from_env` does not read them:
`Resource.create()` already picks up the standard `OTEL_RESOURCE_ATTRIBUTES` via
the SDK's own detector, and a second mechanism for one thing only confuses. The
`resource_attributes` field stays for programmatic configuration.

```yaml
env:
  - name: POD_NAME
    valueFrom:
      fieldRef:
        fieldPath: metadata.name
  - name: OTEL_RESOURCE_ATTRIBUTES
    value: "k8s.pod.name=$(POD_NAME),k8s.namespace.name=$(POD_NS)"
```

`instrument_runtime()` collects `system.*` metrics from `/proc`, which inside a
container is the node's — `system.memory.usage` would report the whole host once
per pod. cAdvisor already reports the container's side of that, so ask for the
process's own metrics only:

```python
instrument_runtime(system_metrics=False)  # process.* and cpython.*, no system.*
```

Collecting logs from container stdout instead of OTLP means `YAOL_EXPORT_LOGS=false`;
the stdout handler stays.

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

worker = spawn(run_forever())  # clean context, its own traces
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
