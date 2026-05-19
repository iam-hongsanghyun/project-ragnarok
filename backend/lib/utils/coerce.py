from __future__ import annotations

from typing import Any

import numpy as np


def number(value: Any, default: float = 0.0) -> float:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    if np.isnan(parsed) or np.isinf(parsed):
        return default
    return parsed


def text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    string = str(value).strip()
    return string if string else default


def bool_value(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    return str(value).lower() in {"1", "true", "yes", "y"}


def put_if_present(
    kwargs: dict[str, Any],
    row: dict[str, Any],
    key: str,
    *,
    coerce: Any = None,
    target_key: str | None = None,
) -> None:
    """Copy `row[key]` into `kwargs` only if the value is present (not None / "").

    Lets us pass through workbook data without fabricating defaults: if the
    user didn't write a value, PyPSA's own component default applies.

    Args:
        kwargs:     dict that will be unpacked into `network.add(...)`.
        row:        a workbook row.
        key:        column name in the workbook.
        coerce:     optional callable (e.g. `number`, `bool_value`, `int`,
                    `text`) applied to the raw value before storing.
        target_key: kwarg name in PyPSA; defaults to `key`.
    """
    v = row.get(key)
    if v is None or v == "":
        return
    out_key = target_key if target_key is not None else key
    kwargs[out_key] = coerce(v) if coerce is not None else v
