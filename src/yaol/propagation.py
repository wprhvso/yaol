from collections.abc import Mapping, MutableMapping

from opentelemetry.context import Context
from opentelemetry.propagate import extract, inject


def inject_headers(
    carrier: MutableMapping[str, str] | None = None,
) -> MutableMapping[str, str]:
    target: MutableMapping[str, str] = {} if carrier is None else carrier
    inject(target)
    return target


def extract_context(carrier: Mapping[str, str]) -> Context:
    return extract(carrier)
