"""
ragnarok-renewable-floor — constraint-pack sample plugin
=========================================================
Stage : in-solve
Hook  : add_constraints(network, model, scenario, options) -> None

Called inside PyPSA's extra_functionality callback, after the linopy model has
been built but before the solver runs.  Modifies network.model in-place by
adding a minimum renewable generation share constraint.

Constraint (per snapshot t):

    Σ p[g, t]  (g ∈ renewables)  ≥  floor · Σ p[g, t]  (g ∈ all generators)

where "renewables" are generators whose carrier exactly matches one of the
carriers selected in the module config (``renewable_carriers``).

Config (module.json):
  renewable_carriers  (carrier-select)  — list of carrier names that count as
                                          renewable; populated from the workbook.
  renewable_floor     (number, 0–100%)  — minimum renewable share floor.
"""
from __future__ import annotations

import logging
from typing import Any

import pypsa

logger = logging.getLogger(__name__)

# Default floor percentage when not set via config.
DEFAULT_FLOOR_PCT: float = 20.0

# Fallback keywords used ONLY when no carrier config is provided at all
# (e.g. plugin installed but workbook not yet opened).
_FALLBACK_KEYWORDS = ("wind", "solar", "hydro", "biomass", "geothermal", "wave", "tidal")


def add_constraints(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    scenario: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """Add a per-snapshot minimum renewable share constraint.

    Args:
        network:  Built pypsa.Network with linopy model attached as
                  ``network.model``.  Add constraints via ``network.model``.
        model:    Original workbook JSON (read-only).
        scenario: Scenario parameters.
        options:  Run options; ``options["moduleConfig"]`` is injected by the
                  host and contains this module's own config values.
    """
    lm = getattr(network, "model", None)
    if lm is None:
        logger.warning("[renewable-floor] network.model not attached — skipped.")
        return

    module_config = options.get("moduleConfig", {})

    # ── Floor fraction ────────────────────────────────────────────────────────
    floor_pct = float(module_config.get("renewable_floor", DEFAULT_FLOOR_PCT))
    floor = floor_pct / 100.0
    if floor <= 0:
        logger.info("[renewable-floor] floor_pct=%.0f — constraint disabled.", floor_pct)
        return

    # ── Identify renewable generators ─────────────────────────────────────────
    gens = network.generators
    if gens.empty:
        logger.warning("[renewable-floor] No generators — skipped.")
        return

    renewable_carriers_cfg = module_config.get("renewable_carriers", None)

    if renewable_carriers_cfg and isinstance(renewable_carriers_cfg, list) and len(renewable_carriers_cfg) > 0:
        # Exact match against user-selected carriers
        renewable_mask = gens["carrier"].isin(renewable_carriers_cfg)
        match_method = f"exact match ({len(renewable_carriers_cfg)} selected carriers)"
    else:
        # Fallback: keyword substring matching (no carriers configured yet)
        renewable_mask = gens["carrier"].str.lower().str.contains(
            "|".join(_FALLBACK_KEYWORDS), na=False
        )
        match_method = "keyword fallback"

    renewable_idx = gens.index[renewable_mask].tolist()

    if not renewable_idx:
        logger.warning(
            "[renewable-floor] No renewable generators found via %s — skipped.",
            match_method,
        )
        return

    # ── Locate the generator dispatch variable in the linopy model ────────────
    p = lm.variables.get("Generator-p")
    if p is None:
        logger.warning(
            "[renewable-floor] Variable 'Generator-p' not found in linopy model. "
            "Available: %s — skipped.",
            list(lm.variables),
        )
        return

    # Identify the generator-axis dimension (non-snapshot dim)
    gen_dim = next(
        (dim for dim in p.dims if "snapshot" not in dim.lower()),
        None,
    )
    if gen_dim is None:
        logger.warning(
            "[renewable-floor] Could not identify generator dimension in %s — skipped.",
            p.dims,
        )
        return

    valid_coords = list(p.coords[gen_dim].values)
    renewable_in_model = [g for g in renewable_idx if g in valid_coords]
    all_in_model = valid_coords

    if not renewable_in_model:
        logger.warning(
            "[renewable-floor] None of the renewable generators appear in the LP "
            "variable — skipped."
        )
        return

    logger.info(
        "[renewable-floor] %.0f%% floor | %d/%d generators renewable | method: %s",
        floor_pct, len(renewable_in_model), len(all_in_model), match_method,
    )

    try:
        p_renew = p.sel({gen_dim: renewable_in_model}).sum(gen_dim)
        p_total = p.sel({gen_dim: all_in_model}).sum(gen_dim)

        lm.add_constraints(
            p_renew - floor * p_total >= 0,
            name="ragnarok_renewable_floor",
        )
        logger.info("[renewable-floor] Constraint 'ragnarok_renewable_floor' registered.")
    except Exception as exc:  # noqa: BLE001
        logger.error("[renewable-floor] Failed to register constraint: %s", exc)
