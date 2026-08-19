from collections.abc import Generator
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from threading import Lock

import grpc
from opentelemetry.proto.collector.logs.v1 import (
    logs_service_pb2,
    logs_service_pb2_grpc,
)
from opentelemetry.proto.collector.metrics.v1 import (
    metrics_service_pb2,
    metrics_service_pb2_grpc,
)
from opentelemetry.proto.collector.trace.v1 import (
    trace_service_pb2,
    trace_service_pb2_grpc,
)
from opentelemetry.proto.common.v1.common_pb2 import KeyValue
from opentelemetry.proto.logs.v1.logs_pb2 import LogRecord
from opentelemetry.proto.metrics.v1.metrics_pb2 import Metric
from opentelemetry.proto.resource.v1.resource_pb2 import Resource
from opentelemetry.proto.trace.v1.trace_pb2 import Span


def _attributes(pairs: list[KeyValue]) -> dict[str, str]:
    return {pair.key: pair.value.string_value for pair in pairs}


class Sink:
    def __init__(self) -> None:
        self._lock = Lock()
        self._traces: list[trace_service_pb2.ExportTraceServiceRequest] = []
        self._logs: list[logs_service_pb2.ExportLogsServiceRequest] = []
        self._metrics: list[metrics_service_pb2.ExportMetricsServiceRequest] = []

    def push_traces(self, request: trace_service_pb2.ExportTraceServiceRequest) -> None:
        with self._lock:
            self._traces.append(request)

    def push_logs(self, request: logs_service_pb2.ExportLogsServiceRequest) -> None:
        with self._lock:
            self._logs.append(request)

    def push_metrics(
        self, request: metrics_service_pb2.ExportMetricsServiceRequest
    ) -> None:
        with self._lock:
            self._metrics.append(request)

    @property
    def spans(self) -> list[Span]:
        with self._lock:
            return [
                span
                for request in self._traces
                for resource_spans in request.resource_spans
                for scope_spans in resource_spans.scope_spans
                for span in scope_spans.spans
            ]

    @property
    def log_records(self) -> list[LogRecord]:
        with self._lock:
            return [
                record
                for request in self._logs
                for resource_logs in request.resource_logs
                for scope_logs in resource_logs.scope_logs
                for record in scope_logs.log_records
            ]

    @property
    def metrics(self) -> list[Metric]:
        with self._lock:
            return [
                metric
                for request in self._metrics
                for resource_metrics in request.resource_metrics
                for scope_metrics in resource_metrics.scope_metrics
                for metric in scope_metrics.metrics
            ]

    def span_named(self, name: str) -> Span:
        return next(span for span in self.spans if span.name == name)

    def log_with_body(self, body: str) -> LogRecord:
        return next(
            record for record in self.log_records if record.body.string_value == body
        )

    def metric_named(self, name: str) -> Metric:
        return next(metric for metric in self.metrics if metric.name == name)

    def _resources(self) -> list[Resource]:
        with self._lock:
            return [
                *(
                    item.resource
                    for request in self._traces
                    for item in request.resource_spans
                ),
                *(
                    item.resource
                    for request in self._logs
                    for item in request.resource_logs
                ),
                *(
                    item.resource
                    for request in self._metrics
                    for item in request.resource_metrics
                ),
            ]

    def resource_attributes(self) -> dict[str, str]:
        merged: dict[str, str] = {}
        for resource in self._resources():
            merged.update(_attributes(list(resource.attributes)))
        return merged

    def clear(self) -> None:
        with self._lock:
            self._traces.clear()
            self._logs.clear()
            self._metrics.clear()


class _TraceService:
    def __init__(self, sink: Sink) -> None:
        self._sink = sink

    def Export(  # noqa: N802
        self,
        request: trace_service_pb2.ExportTraceServiceRequest,
        _context: object,
    ) -> trace_service_pb2.ExportTraceServiceResponse:
        self._sink.push_traces(request)
        return trace_service_pb2.ExportTraceServiceResponse()


class _LogsService:
    def __init__(self, sink: Sink) -> None:
        self._sink = sink

    def Export(  # noqa: N802
        self,
        request: logs_service_pb2.ExportLogsServiceRequest,
        _context: object,
    ) -> logs_service_pb2.ExportLogsServiceResponse:
        self._sink.push_logs(request)
        return logs_service_pb2.ExportLogsServiceResponse()


class _MetricsService:
    def __init__(self, sink: Sink) -> None:
        self._sink = sink

    def Export(  # noqa: N802
        self,
        request: metrics_service_pb2.ExportMetricsServiceRequest,
        _context: object,
    ) -> metrics_service_pb2.ExportMetricsServiceResponse:
        self._sink.push_metrics(request)
        return metrics_service_pb2.ExportMetricsServiceResponse()


class Collector:
    def __init__(self, endpoint: str, sink: Sink) -> None:
        self.endpoint = endpoint
        self.sink = sink


@contextmanager
def running_collector() -> Generator[Collector]:
    sink = Sink()
    server = grpc.server(ThreadPoolExecutor(max_workers=4))
    trace_service_pb2_grpc.add_TraceServiceServicer_to_server(
        _TraceService(sink), server
    )
    logs_service_pb2_grpc.add_LogsServiceServicer_to_server(_LogsService(sink), server)
    metrics_service_pb2_grpc.add_MetricsServiceServicer_to_server(
        _MetricsService(sink), server
    )
    port = server.add_insecure_port("127.0.0.1:0")
    server.start()
    try:
        yield Collector(f"http://127.0.0.1:{port}", sink)
    finally:
        server.stop(grace=None)
        server.wait_for_termination(timeout=5)
