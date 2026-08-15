from collections.abc import Mapping, MutableMapping

from opentelemetry.context import Context
from opentelemetry.propagate import extract, inject


def inject_headers(
    carrier: MutableMapping[str, str] | None = None,
) -> MutableMapping[str, str]:
    """Write the active trace context into a header carrier and return it.

    Only needed for hops no instrumentation covers; instrumented HTTP clients
    inject the headers themselves.
    """
    target: MutableMapping[str, str] = {} if carrier is None else carrier
    inject(target)
    return target


def extract_context(carrier: Mapping[str, str]) -> Context:
    """Rebuild a trace context from incoming headers."""
    return extract(carrier)
