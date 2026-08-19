import yaol


def test_every_exported_name_exists() -> None:
    missing = [name for name in yaol.__all__ if not hasattr(yaol, name)]

    assert missing == []


def test_exports_are_sorted_and_unique() -> None:
    assert yaol.__all__ == sorted(set(yaol.__all__))


def test_the_documented_entry_points_are_exported() -> None:
    documented = {
        "ObservabilityConfig",
        "from_env",
        "setup",
        "shutdown",
        "span",
        "spawn",
        "capture",
        "attached",
        "detached",
        "links",
        "record_exception",
        "fail",
        "inject_headers",
        "extract_context",
        "instrument_fastapi",
        "instrument_httpx",
        "instrument_asyncpg",
    }

    assert documented <= set(yaol.__all__)


def test_the_package_carries_type_information() -> None:
    from importlib.resources import files

    assert files("yaol").joinpath("py.typed").is_file()
