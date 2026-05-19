from __future__ import annotations

from collections import defaultdict
from typing import Any

import numpy as np
import pandas as pd
import pypsa

from ..utils.coerce import number, put_if_present, text
from ..utils.workbook import workbook_rows


def add_buses(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    notes: list[str],
) -> None:
    """Add Bus components. Only `name` is required; every other column is
    optional and passed through only if present (no fabricated defaults)."""
    buses = workbook_rows(model, "buses")
    if not buses:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Workbook has no buses.")
    for row in buses:
        name = text(row.get("name"))
        if not name:
            notes.append("A bus row has no name — skipped.")
            continue
        kwargs: dict[str, Any] = {}
        for col in (
            "x", "y", "v_nom", "v_mag_pu_set", "v_mag_pu_min", "v_mag_pu_max",
        ):
            put_if_present(kwargs, row, col, coerce=number)
        put_if_present(kwargs, row, "carrier", coerce=text)
        put_if_present(kwargs, row, "control", coerce=text)
        put_if_present(kwargs, row, "unit", coerce=text)
        put_if_present(kwargs, row, "sub_network", coerce=text)
        network.add("Bus", name, **kwargs)


def parse_ts_sheet(
    model: dict[str, list[dict[str, Any]]],
    sheet_name: str,
    snapshots: pd.Index,
    snapshot_start: int = 0,
    snapshot_window: int | None = None,
    step: int = 1,
) -> dict[str, np.ndarray] | None:
    """Parse a time-series sheet (rows = timesteps, columns = component names).
    Returns a dict mapping component name → float array aligned to snapshots,
    or None if the sheet is absent or empty.

    When *step* > 1 the TS sheet is downsampled with ``arr[::step]`` before
    alignment, matching the PyPSA convention of selecting every N-th snapshot.
    If the raw row count equals ``len(snapshots)`` (sheet was already
    pre-aggregated) the slice is skipped."""
    rows = model.get(sheet_name) or []
    if not rows:
        return None
    # Identify which keys are timestamp/index columns vs data columns
    index_keys = {"snapshot", "datetime", "name", "index", "timestep"}
    data_keys = [k for k in rows[0].keys() if k.lower() not in index_keys]
    if not data_keys:
        return None
    result: dict[str, np.ndarray] = {}
    n_snap = len(snapshots)
    for key in data_keys:
        vals = [number(r.get(key), 0.0) for r in rows]
        arr = np.array(vals, dtype=float)
        if len(arr) != n_snap:
            stop = len(arr) if snapshot_window is None else min(len(arr), snapshot_start + snapshot_window)
            arr = arr[snapshot_start:stop]
            if step > 1:
                arr = arr[::step]
        if len(arr) == n_snap:
            result[key] = arr
    return result if result else None


def add_loads(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    snapshots: pd.Index,
    notes: list[str],
    snapshot_start: int = 0,
    snapshot_window: int | None = None,
    step: int = 1,
) -> dict[str, float]:
    """Add loads using workbook data only.
    If 'loads-p_set' sheet is present its time-series takes priority;
    otherwise the static p_set is used as a flat constant.
    Optional columns (carrier, sign, etc.) are passed through only when
    present — no fabricated defaults.
    """
    ts_p_set = parse_ts_sheet(
        model,
        "loads-p_set",
        snapshots,
        snapshot_start=snapshot_start,
        snapshot_window=snapshot_window,
        step=step,
    )
    load_totals: dict[str, float] = defaultdict(float)

    for row in workbook_rows(model, "loads"):
        name = text(row.get("name"))
        bus = text(row.get("bus"))
        if not name:
            notes.append("A load row has no name — skipped.")
            continue
        if bus not in network.buses.index:
            notes.append(f"Load '{name}' references non-existent bus '{bus}' — skipped.")
            continue
        p_set_static = number(row.get("p_set"), 0.0)
        load_kwargs: dict[str, Any] = {"bus": bus}
        put_if_present(load_kwargs, row, "carrier", coerce=text)
        put_if_present(load_kwargs, row, "q_set", coerce=number)
        put_if_present(load_kwargs, row, "sign", coerce=number)
        network.add("Load", name, **load_kwargs)
        if ts_p_set and name in ts_p_set:
            network.loads_t.p_set.loc[:, name] = ts_p_set[name]
        else:
            network.loads_t.p_set.loc[:, name] = p_set_static
        load_totals[bus] += p_set_static
    return dict(load_totals)
