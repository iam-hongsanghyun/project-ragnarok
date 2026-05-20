"""
ragnarok-log-importer — data-importer sample plugin
====================================================
Stage : pre-build
Hook  : transform(model, scenario, options) -> model

Called before build_network(). Receives the full workbook JSON as a dict of
sheet-name → list[row-dict] and returns a (possibly modified) model.  This
sample logs a human-readable summary of the incoming data and returns the model
unchanged — useful as a debugging baseline or starting point for a real importer.

Config (module.json):
  verbose       (bool, default True)  — log per-sheet row counts and snapshot range.
  log_scenario  (bool, default True)  — include carbonPrice / discountRate in output.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

COMPONENT_SHEETS = [
    "buses", "generators", "loads", "lines", "links",
    "stores", "storage_units", "transformers",
]


def transform(
    model: dict[str, list[dict[str, Any]]],
    scenario: dict[str, Any],
    options: dict[str, Any],
) -> dict[str, list[dict[str, Any]]]:
    """Log a model summary and return the model unchanged.

    Args:
        model:    Workbook JSON — keys are sheet names, values are row lists.
        scenario: Scenario parameters (carbonPrice, discountRate, …).
        options:  Run options (snapshotWeight, snapshotStart, …).
                  ``options["moduleConfig"]`` is injected by the host and
                  contains this module's own config values.

    Returns:
        The model dict unmodified.
    """
    module_config = options.get("moduleConfig", {})
    verbose      = bool(module_config.get("verbose",      True))
    log_scenario = bool(module_config.get("log_scenario", True))

    logger.info("[log-importer] ── incoming model ──────────────────")

    if verbose:
        for sheet in COMPONENT_SHEETS:
            rows = [r for r in (model.get(sheet) or []) if r.get("name")]
            if rows:
                logger.info("[log-importer]   %-20s %d rows", sheet, len(rows))

        snapshots = model.get("snapshots") or []
        if snapshots:
            first = snapshots[0].get("snapshot") or snapshots[0].get("name") or "?"
            last  = snapshots[-1].get("snapshot") or snapshots[-1].get("name") or "?"
            logger.info("[log-importer]   %-20s %d rows  [%s … %s]",
                        "snapshots", len(snapshots), first, last)
    else:
        total = sum(
            len([r for r in (model.get(s) or []) if r.get("name")])
            for s in COMPONENT_SHEETS
        )
        logger.info("[log-importer]   %d component rows across all sheets", total)

    if log_scenario:
        logger.info(
            "[log-importer]   carbonPrice=%.2f  discountRate=%.4f  snapshotWeight=%s",
            float(scenario.get("carbonPrice", 0)),
            float(scenario.get("discountRate", 0)),
            options.get("snapshotWeight", 1),
        )

    logger.info("[log-importer] ────────────────────────────────────")

    return model          # replace this dict to transform the model
