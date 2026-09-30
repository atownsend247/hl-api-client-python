import dataclasses
from collections.abc import Iterable
from typing import Any, TextIO

_SEPARATOR = ","


def _quote_field(field: str) -> str:
    if not field:
        return '""'
    if any(c in field for c in (_SEPARATOR, '"', "\r", "\n")):
        return '"' + field.replace('"', '""') + '"'
    return field


def _quote_record(record: Iterable[str]) -> str:
    return _SEPARATOR.join(_quote_field(f) for f in record)


def serialize(output: TextIO, objects: Iterable[Any], record_type: type | None = None) -> None:
    """Serialize dataclass instances to Comma Separated Value (CSV) format (RFC 4180).

    Rather than serializing arbitrarily complex types, prefer mapping them to a flat dataclass first.

    Args:
        output: Where to write.
        objects: The dataclass instances to write.
        record_type: The dataclass to take the header from. Only needed when ``objects`` may be empty and
            you still want the header row written.
    """
    records = list(objects)
    if record_type is None and records:
        record_type = type(records[0])
    if record_type is None:
        return

    names = [f.name for f in dataclasses.fields(record_type)]
    output.write(_quote_record(names) + "\n")
    for record in records:
        values = (getattr(record, n) for n in names)
        output.write(_quote_record("" if v is None else str(v) for v in values) + "\n")
