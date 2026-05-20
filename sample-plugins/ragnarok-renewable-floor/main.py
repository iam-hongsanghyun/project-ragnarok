"""
ragnarok-renewable-floor — constraint-pack sample plugin
=========================================================
Stage : in-solve
Hook  : add_constraints(network, model, scenario, options) -> None

Called inside PyPSA's extra_functionality callback, after the linopy model has
been built but before the solver runs.  Modifies n.model in-place by adding a
minimum renewable energy-share constraint over the full optimisation horizon:

    Σ_t Σ_{g ∈ renewables} w_t · p[g,t]
        ≥  floor · Σ_t Σ_{g ∈ all} w_t · p[g,t]

where w_t is the snapshot weighting (matches PyPSA's objective weighting).

Config (module.json):
  renewable_carriers  (carrier-select)  — exact carrier names that count as
                                          renewable; populated from workbook.
  renewable_floor     (number, 0–100%)  — minimum renewable share.
"""
from __future__ import annotations

import logging
from typing import Any

import pypsa

logger = logging.getLogger(__name__)

DEFAULT_FLOOR_PCT: float = 20.0

# Keyword fallback used only when no carriers are configured yet.
_FALLBACK_KEYWORDS = ("wind", "solar", "hydro", "biomass", "geothermal", "wave", "tidal")


def add_constraints(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    scenario: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """Add a minimum renewable energy-share constraint.

    Args:
        network:  pypsa.Network with linopy model at ``network.model``.
        model:    Workbook JSON (read-only).
        scenario: Scenario parameters.
        options:  Run options; ``options["moduleConfig"]`` contains this
                  module's own config values injected by the host.
    """
    n = network
    lm = getattr(n, "model", None)
    if lm is None:
        logger.warning("[renewable-floor] n.model not attached — skipped.")
        return

    module_config = options.get("moduleConfig", {})

    # ── Floor fraction ─────────────────────────────────────────────────────────
    floor_pct = float(module_config.get("renewable_floor", DEFAULT_FLOOR_PCT))
    floor = floor_pct / 100.0
    if floor <= 0:
        logger.info("[renewable-floor] floor_pct=%.0f — constraint disabled.", floor_pct)
        return

    # ── Generator variable — use subscript access, same as custom_constraints.py
    try:
        gen_p = lm["Generator-p"]
    except KeyError:
        available = list(lm.variables)
        logger.warning(
            "[renewable-floor] Variable 'Generator-p' not in linopy model. "
            "Available: %s — skipped.", available,
        )
        return

    # Generator dimension (non-snapshot axis)
    dim = next((d for d in gen_p.dims if d != "snapshot" and "snapshot" not in d.lower()), None)
    if dim is None:
        logger.warning("[renewable-floor] Cannot identify generator dim in %s — skipped.", gen_p.dims)
        return

    # Snapshot weights (matches PyPSA's objective weighting)
    weights = n.snapshot_weightings["generators"]

    # ── Identify renewable generators ──────────────────────────────────────────
    gens = n.generators
    if gens.empty:
        logger.warning("[renewable-floor] No generators — skipped.")
        return

    renewable_carriers_cfg = module_config.get("renewable_carriers", None)

    if renewable_carriers_cfg and isinstance(renewable_carriers_cfg, list) and len(renewable_carriers_cfg) > 0:
        renewable_mask = gens["carrier"].isin(renewable_carriers_cfg)
        match_method = f"exact match ({len(renewable_carriers_cfg)} selected carriers)"
    else:
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

    # Intersect with generators that actually appear in the LP variable
    valid_coords = set(gen_p.coords[dim].values.tolist())
    renewable_in_lp = [g for g in renewable_idx    if g in valid_coords]
    all_in_lp       = [g for g in gens.index.tolist() if g in valid_coords]

    if not renewable_in_lp:
        logger.warning(
            "[renewable-floor] None of the %d renewable generators appear in the LP "
            "variable — skipped.", len(renewable_idx),
        )
        return

    logger.info(
        "[renewable-floor] %.0f%% floor | %d/%d generators renewable | %s",
        floor_pct, len(renewable_in_lp), len(all_in_lp), match_method,
    )

    # ── Build constraint — energy-share over full horizon ─────────────────────
    # Same pattern as carrier_min_share in custom_constraints.py:
    #   (gen_p.sel({dim: gens}) * weights).sum() — scalar linopy expression
    try:
        renew_energy = (gen_p.sel({dim: renewable_in_lp}) * weights).sum()
        total_energy = (gen_p.sel({dim: all_in_lp})       * weights).sum()

        n.model.add_constraints(
            renew_energy - floor * total_energy >= 0,
            name="ragnarok_renewable_floor",
        )
        logger.info(
            "[renewable-floor] Constraint 'ragnarok_renewable_floor' registered "
            "(%.0f%% of total energy must be renewable).", floor_pct,
        )
    except Exception as exc:
        # Re-raise so the infeasibility surfaces properly rather than being swallowed.
        logger.error("[renewable-floor] Failed to register constraint: %s", exc)
        raise
