import pytest

from yaol.config import (
    DEFAULT_OTLP_ENDPOINT,
    DEFAULT_PYROSCOPE_ADDRESS,
    ObservabilityConfig,
    from_env,
)

_KEYS = (
    "ENV",
    "OTEL_EXPORTER_OTLP_ENDPOINT",
    "OTEL_EXPORTER_OTLP_INSECURE",
    "LOG_LEVEL",
    "YAOL_JSON_LOGS",
    "YAOL_EXPORT_TRACES",
    "YAOL_EXPORT_LOGS",
    "YAOL_EXPORT_METRICS",
    "YAOL_METRIC_INTERVAL_MILLIS",
    "YAOL_TRACE_SAMPLE_RATIO",
    "YAOL_SPAN_QUEUE_SIZE",
    "YAOL_SPAN_SCHEDULE_DELAY_MILLIS",
    "YAOL_SPAN_EXPORT_BATCH_SIZE",
    "YAOL_PROFILING_ENABLED",
    "PYROSCOPE_ADDRESS",
    "PYROSCOPE_SAMPLE_RATE",
    "PYROSCOPE_ONCPU",
    "PYROSCOPE_GIL_ONLY",
    "PYROSCOPE_REPORT_PID",
    "PYROSCOPE_REPORT_THREAD_ID",
    "PYROSCOPE_TAGS",
)


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in _KEYS:
        monkeypatch.delenv(key, raising=False)


def test_defaults_are_stable() -> None:
    config = ObservabilityConfig(service_name="bot")

    assert config.otlp_endpoint == DEFAULT_OTLP_ENDPOINT
    assert config.pyroscope_address == DEFAULT_PYROSCOPE_ADDRESS
    assert config.json_logs is None
    assert config.profiling_enabled is False
    assert config.export_traces is True
    assert config.trace_sample_ratio == 1.0


def test_config_is_immutable() -> None:
    config = ObservabilityConfig(service_name="bot")
    field = "service_name"

    with pytest.raises(AttributeError):
        setattr(config, field, "other")


def test_mappings_are_not_shared_between_instances() -> None:
    first = ObservabilityConfig(service_name="a")
    second = ObservabilityConfig(service_name="b")

    assert first.logger_levels is not second.logger_levels
    assert first.resource_attributes == {}


def test_env_defaults_match_the_dataclass() -> None:
    assert from_env("bot") == ObservabilityConfig(service_name="bot")


def test_from_env_reads_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://172.17.0.1:4317")
    monkeypatch.setenv("ENV", "dev")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("YAOL_PROFILING_ENABLED", "true")
    monkeypatch.setenv("YAOL_METRIC_INTERVAL_MILLIS", "5000")
    monkeypatch.setenv("YAOL_SPAN_QUEUE_SIZE", "128")
    monkeypatch.setenv("YAOL_SPAN_SCHEDULE_DELAY_MILLIS", "250")
    monkeypatch.setenv("YAOL_SPAN_EXPORT_BATCH_SIZE", "64")
    monkeypatch.setenv("YAOL_TRACE_SAMPLE_RATIO", "0.25")
    monkeypatch.setenv("PYROSCOPE_ADDRESS", "http://pyroscope:4040")
    monkeypatch.setenv("PYROSCOPE_SAMPLE_RATE", "50")

    config = from_env("bot", service_version="1.2.3")

    assert config.otlp_endpoint == "http://172.17.0.1:4317"
    assert config.environment == "dev"
    assert config.log_level == "DEBUG"
    assert config.profiling_enabled is True
    assert config.metric_interval_millis == 5000
    assert config.span_queue_size == 128
    assert config.span_schedule_delay_millis == 250
    assert config.span_export_batch_size == 64
    assert config.trace_sample_ratio == 0.25
    assert config.pyroscope_address == "http://pyroscope:4040"
    assert config.pyroscope_sample_rate == 50
    assert config.service_version == "1.2.3"


@pytest.mark.parametrize("raw", ["1", "true", "TRUE", " yes ", "on"])
def test_truthy_flags(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("YAOL_PROFILING_ENABLED", raw)

    assert from_env("bot").profiling_enabled is True


@pytest.mark.parametrize("raw", ["0", "false", "no", "off", "", "maybe"])
def test_falsey_flags(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("YAOL_EXPORT_TRACES", raw)

    assert from_env("bot").export_traces is False


def test_explicit_argument_loses_to_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENV", "dev")

    assert from_env("bot", environment="prod").environment == "dev"


def test_explicit_argument_wins_when_the_variable_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ENV", "")

    assert from_env("bot", environment="staging").environment == "staging"


def test_json_logs_stays_undecided_without_a_variable() -> None:
    assert from_env("bot").json_logs is None


@pytest.mark.parametrize(("raw", "expected"), [("1", True), ("0", False)])
def test_json_logs_is_decided_by_the_variable(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
) -> None:
    monkeypatch.setenv("YAOL_JSON_LOGS", raw)

    assert from_env("bot").json_logs is expected


def test_invalid_number_falls_back(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("YAOL_METRIC_INTERVAL_MILLIS", "not-a-number")

    assert from_env("bot").metric_interval_millis == 30000


@pytest.mark.parametrize("raw", ["0", "-1"])
def test_non_positive_number_falls_back(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("YAOL_SPAN_QUEUE_SIZE", raw)

    assert from_env("bot").span_queue_size == 4096


@pytest.mark.parametrize(
    ("raw", "expected"),
    [("2", 1.0), ("-1", 0.0), ("0", 0.0), ("0.5", 0.5)],
)
def test_ratio_is_clamped(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: float
) -> None:
    monkeypatch.setenv("YAOL_TRACE_SAMPLE_RATIO", raw)

    assert from_env("bot").trace_sample_ratio == expected


@pytest.mark.parametrize("raw", ["nan", "banana"])
def test_unusable_ratio_falls_back(monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
    monkeypatch.setenv("YAOL_TRACE_SAMPLE_RATIO", raw)

    assert from_env("bot").trace_sample_ratio == 1.0


def test_insecure_can_be_turned_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_INSECURE", "false")

    assert from_env("bot").otlp_insecure is False


def test_pyroscope_flags_are_read_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYROSCOPE_ONCPU", "false")
    monkeypatch.setenv("PYROSCOPE_GIL_ONLY", "off")
    monkeypatch.setenv("PYROSCOPE_REPORT_PID", "true")
    monkeypatch.setenv("PYROSCOPE_REPORT_THREAD_ID", "1")

    config = from_env("bot")

    assert config.pyroscope_oncpu is False
    assert config.pyroscope_gil_only is False
    assert config.pyroscope_report_pid is True
    assert config.pyroscope_report_thread_id is True


def test_pyroscope_tags_are_read_as_pairs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYROSCOPE_TAGS", "pod=bot-7d9f4,namespace=prod")

    assert from_env("bot").pyroscope_tags == {"pod": "bot-7d9f4", "namespace": "prod"}


def test_pyroscope_tags_lose_their_padding(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYROSCOPE_TAGS", "  pod = bot-7d9f4 ,\tnamespace = prod\n")

    assert from_env("bot").pyroscope_tags == {"pod": "bot-7d9f4", "namespace": "prod"}


def test_pyroscope_tags_are_empty_without_a_variable() -> None:
    assert from_env("bot").pyroscope_tags == {}


@pytest.mark.parametrize("raw", ["", "   ", "pod", "pod,namespace", "=prod", " = prod"])
def test_unusable_pyroscope_tags_leave_nothing_behind(
    monkeypatch: pytest.MonkeyPatch, raw: str
) -> None:
    monkeypatch.setenv("PYROSCOPE_TAGS", raw)

    assert from_env("bot").pyroscope_tags == {}


def test_a_broken_pyroscope_tag_does_not_take_the_others_with_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYROSCOPE_TAGS", "pod,=prod,namespace=prod")

    assert from_env("bot").pyroscope_tags == {"namespace": "prod"}


def test_a_pyroscope_tag_value_may_contain_equals_signs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PYROSCOPE_TAGS", "selector=app=bot")

    assert from_env("bot").pyroscope_tags == {"selector": "app=bot"}


def test_the_last_pyroscope_tag_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PYROSCOPE_TAGS", "pod=first,pod=second")

    assert from_env("bot").pyroscope_tags == {"pod": "second"}
