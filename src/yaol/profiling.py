import structlog

from yaol.config import ObservabilityConfig

log = structlog.get_logger("yaol")

_active = False


def setup_profiling(config: ObservabilityConfig) -> bool:
    global _active  # noqa: PLW0603

    if not config.profiling_enabled:
        return False

    try:
        import pyroscope
    except ImportError:
        log.warning("pyroscope_unavailable", address=config.pyroscope_address)
        return False

    tags = {
        "env": config.environment,
        "version": config.service_version,
        **dict(config.pyroscope_tags),
    }

    try:
        pyroscope.configure(
            application_name=config.service_name,
            server_address=config.pyroscope_address,
            sample_rate=config.pyroscope_sample_rate,
            oncpu=config.pyroscope_oncpu,
            gil_only=config.pyroscope_gil_only,
            report_pid=config.pyroscope_report_pid,
            report_thread_id=config.pyroscope_report_thread_id,
            tags=tags,
        )
    except (OSError, RuntimeError, ValueError):
        log.exception("pyroscope_not_started", address=config.pyroscope_address)
        return False

    _active = True
    log.info("pyroscope_started", address=config.pyroscope_address)
    return True


def shutdown_profiling() -> None:
    global _active  # noqa: PLW0603

    if not _active:
        return

    try:
        import pyroscope

        pyroscope.shutdown()
    except (ImportError, OSError, RuntimeError):
        log.exception("pyroscope_not_stopped")
    finally:
        _active = False
