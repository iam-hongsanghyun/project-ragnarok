"""
ragnarok-dashboard-importer — portable dashboard importer
=========================================================
Stage : pre-build
Hook  : transform(model, scenario, options) -> model

This plugin vendors the dashboard-driven pre-optimisation pipeline used by
simplePyPSA_KR and returns the built case as a Ragnarok workbook model.

Inputs required at runtime:
- a ``dashboard.xlsx`` workbook
- the model workbook referenced by the dashboard's ``network`` sheet

No local ``simplePyPSA_KR`` source checkout is required on the target machine.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime
import importlib
import logging
import math
from pathlib import Path
import sys
from typing import Any, Iterator

import pandas as pd

logger = logging.getLogger(__name__)

PLUGIN_ROOT = Path(__file__).resolve().parent

MODEL_SHEETS = [
    "network",
    "snapshots",
    "carriers",
    "buses",
    "generators",
    "loads",
    "links",
    "lines",
    "stores",
    "storage_units",
    "transformers",
    "shunt_impedances",
    "global_constraints",
    "shapes",
    "processes",
    "generators-p_max_pu",
    "generators-p_min_pu",
    "loads-p_set",
    "storage_units-inflow",
    "links-p_max_pu",
]

TS_SHEET_ATTRS = {
    "generators-p_max_pu": ("generators", "p_max_pu"),
    "generators-p_min_pu": ("generators", "p_min_pu"),
    "loads-p_set": ("loads", "p_set"),
    "storage_units-inflow": ("storage_units", "inflow"),
    "links-p_max_pu": ("links", "p_max_pu"),
}

PASS_THROUGH_IF_IMPORT_EMPTY = {
    "global_constraints",
    "shapes",
    "processes",
}


def transform(
    model: dict[str, list[dict[str, Any]]],
    scenario: dict[str, Any],
    options: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Build a Ragnarok workbook model from dashboard.xlsx."""
    del scenario

    module_config = options.get("moduleConfig", {})
    dashboard_path = _resolve_dashboard_path(module_config)
    export_path = _resolve_export_path(module_config, dashboard_path.parent)

    logger.info("[dashboard-importer] dashboard=%s", dashboard_path)

    network = _build_dashboard_network(dashboard_path)
    imported_model = _network_to_model(network)

    if export_path is not None:
        _write_model_workbook(imported_model, export_path)
        logger.info("[dashboard-importer] wrote debug workbook to %s", export_path)

    merged_model = _merge_with_existing_model(imported_model, model, module_config)
    logger.info(
        "[dashboard-importer] imported %d buses, %d generators, %d loads, %d snapshots",
        len(merged_model["buses"]),
        len(merged_model["generators"]),
        len(merged_model["loads"]),
        len(merged_model["snapshots"]),
    )
    return merged_model


def _build_dashboard_network(dashboard_path: Path):
    with _bundled_lib_path():
        settings_mod = importlib.import_module("dashboard_lib.settings")
        loader_mod = importlib.import_module("dashboard_lib.loader")
        topology_mod = importlib.import_module("dashboard_lib.topology")
        region_mod = importlib.import_module("dashboard_lib.region")
        carrier_mod = importlib.import_module("dashboard_lib.carrier")
        scaling_mod = importlib.import_module("dashboard_lib.scaling")
        snapshots_mod = importlib.import_module("dashboard_lib.snapshots")
        merge_cc_mod = importlib.import_module("dashboard_lib.merge_cc")
        p_max_pu_mod = importlib.import_module("dashboard_lib.p_max_pu")

    dashboard = settings_mod.read_dashboard(dashboard_path)
    dashboard.settings.model = str(_resolve_model_path(dashboard.settings.model, dashboard_path))

    settings = dashboard.settings
    network = loader_mod.build_network_for_year(settings.model, settings.target_year)
    loader_mod.select_base_year_temporal(network, settings.base_year)
    merge_cc_mod.merge_cc_generators(network, dashboard)
    topology_mod.apply_topology(network, settings)
    region_mod.aggregate_by_region(network, dashboard)
    scaling_mod.scale_load(network, settings.target_load_twh)
    p_max_pu_mod.apply_standard_p_max_pu(network, settings.model)
    carrier_mod.aggregate_by_carrier(network, dashboard)
    snapshots_mod.slice_snapshots(network, settings.snapshot_start, settings.snapshot_length)
    topology_mod.drop_components_with_missing_buses(network)
    return network


def _resolve_dashboard_path(module_config: dict[str, Any]) -> Path:
    raw = str(module_config.get("dashboard_path", "")).strip()
    if not raw:
        raise ValueError("dashboard_path is required.")
    path = _resolve_path(raw)
    if not path.exists():
        raise ValueError(f"dashboard_path does not exist: {path}")
    return path


def _resolve_export_path(module_config: dict[str, Any], base: Path) -> Path | None:
    raw = str(module_config.get("export_path", "")).strip()
    if not raw:
        return None
    return _resolve_path(raw, base=base)


def _resolve_model_path(raw_model_path: str, dashboard_path: Path) -> Path:
    model_path = Path(str(raw_model_path).strip()).expanduser()
    if model_path.is_absolute():
        resolved = model_path.resolve()
    else:
        resolved = (dashboard_path.parent / model_path).resolve()
    if not resolved.exists():
        raise ValueError(f"Dashboard model workbook does not exist: {resolved}")
    return resolved


def _resolve_path(raw: str, base: Path | None = None) -> Path:
    text = raw.replace("${HOME}", str(Path.home()))
    text = text.replace("${PROJECT_ROOT}", str(Path.cwd()))
    path = Path(text).expanduser()
    if not path.is_absolute():
        path = (base or Path.cwd()) / path
    return path.resolve()


@contextmanager
def _bundled_lib_path() -> Iterator[None]:
    root_text = str(PLUGIN_ROOT)
    sys.path.insert(0, root_text)
    try:
        yield
    finally:
        if sys.path and sys.path[0] == root_text:
            sys.path.pop(0)


def _network_to_model(network: Any) -> dict[str, list[dict[str, Any]]]:
    model = _empty_model()

    snapshots = []
    for snapshot in network.snapshots:
        row = {"snapshot": _normalize_scalar(snapshot)}
        for col in ("objective", "stores", "generators"):
            if col in network.snapshot_weightings.columns:
                row[col] = _normalize_scalar(network.snapshot_weightings.at[snapshot, col])
        snapshots.append(row)
    model["snapshots"] = snapshots

    model["network"] = [{"name": str(network.name)}] if getattr(network, "name", "") else []

    for component in network.iterate_components():
        sheet_name = component.list_name
        if sheet_name in model:
            model[sheet_name] = _frame_to_rows(component.df)

    for sheet_name, (component_name, attr) in TS_SHEET_ATTRS.items():
        pnl = getattr(network, f"{component_name}_t", None)
        if pnl is None:
            continue
        df = getattr(pnl, attr, None)
        if df is None or df.empty:
            continue
        out = df.copy()
        out.index.name = out.index.name or "snapshot"
        model[sheet_name] = _frame_to_rows(out.reset_index(), preserve_index=False)

    return model


def _frame_to_rows(frame: pd.DataFrame, preserve_index: bool = True) -> list[dict[str, Any]]:
    if frame is None or frame.empty:
        return []
    out = frame.copy()
    if preserve_index:
        out.index.name = out.index.name or "name"
        out = out.reset_index()
    rows = []
    for raw_row in out.to_dict(orient="records"):
        row = {str(key): _normalize_scalar(value) for key, value in raw_row.items()}
        if any(value not in (None, "") for value in row.values()):
            rows.append(row)
    return rows


def _write_model_workbook(model: dict[str, list[dict[str, Any]]], export_path: Path) -> None:
    export_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(export_path, engine="openpyxl") as writer:
        for sheet in MODEL_SHEETS:
            rows = model.get(sheet) or []
            if not rows:
                continue
            pd.DataFrame(rows).to_excel(writer, sheet_name=sheet, index=False)


def _normalize_scalar(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if hasattr(value, "item") and callable(value.item):
        try:
            value = value.item()
        except Exception:
            pass
    if isinstance(value, pd.Timestamp):
        return value.isoformat(sep=" ")
    if isinstance(value, datetime):
        return value.isoformat(sep=" ")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        if isinstance(value, float) and not math.isfinite(value):
            return None
        return value
    if isinstance(value, str):
        return value
    return str(value)


def _merge_with_existing_model(
    imported_model: dict[str, list[dict[str, Any]]],
    incoming_model: dict[str, list[dict[str, Any]]],
    module_config: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    merged = _empty_model()
    preserve_existing_loads = bool(module_config.get("preserve_existing_loads", False))

    for sheet in MODEL_SHEETS:
        imported_rows = list(imported_model.get(sheet) or [])
        incoming_rows = list(incoming_model.get(sheet) or [])

        if sheet in PASS_THROUGH_IF_IMPORT_EMPTY and not imported_rows and incoming_rows:
            merged[sheet] = incoming_rows
            continue

        if preserve_existing_loads and sheet in {"loads", "loads-p_set"} and incoming_rows:
            merged[sheet] = incoming_rows
            continue

        merged[sheet] = imported_rows if imported_rows else incoming_rows

    return merged


def _empty_model() -> dict[str, list[dict[str, Any]]]:
    return {sheet: [] for sheet in MODEL_SHEETS}
