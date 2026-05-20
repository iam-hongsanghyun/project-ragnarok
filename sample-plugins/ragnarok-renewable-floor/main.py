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

Renewable carriers are identified by substring match against RENEWABLE_KEYWORDS.
The floor fraction defaults to 0.20 and can be overridden by setting
``renewable_floor`` in the scenario dict (e.g. from a future module-config UI).
"""
from __future__ import annotations

import logging
from typing import Any

import pypsa

logger = logging.getLogger(__name__)

# Default floor as a percentage (0–100); divide by 100 before use.
DEFAULT_FLOOR_PCT: float = 20.0
RENEWABLE_KEYWORDS = ("wind", "solar", "hydro", "biomass", "geothermal", "wave", "tidal")


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
        scenario: Scenario parameters; reads ``renewable_floor`` if present.
        options:  Run options.
    """
    lm = getattr(network, "model", None)
    if lm is None:
        logger.warning("[renewable-floor] network.model not attached — skipped.")
        return

    # Read floor from the module's own config (set via the UI card).
    # The backend injects options["moduleConfig"] with this module's values.
    module_config = options.get("moduleConfig", {})
    floor_pct = float(module_config.get("renewable_floor", DEFAULT_FLOOR_PCT))
    floor = floor_pct / 100.0

    if floor <= 0:
        logger.info("[renewable-floor] floor_pct=%.0f — constraint disabled.", floor_pct)
        return

    gens = network.generators
    if gens.empty:
        logger.warning("[renewable-floor] No generators — skipped.")
        return

    renewable_mask = gens["carrier"].str.lower().str.contains(
        "|".join(RENEWABLE_KEYWORDS), na=False
    )
    renewable_idx = gens.index[renewable_mask].tolist()

    if not renewable_idx:
        logger.warning(
            "[renewable-floor] No renewable generators found (keywords: %s) — skipped.",
            RENEWABLE_KEYWORDS,
        )
        return

    # ── Locate the generator dispatch variable in the linopy model ────────────
    # PyPSA names the variable "Generator-p"; the generator dimension is the
    # component index dimension (label varies by PyPSA version).
    p = lm.variables.get("Generator-p")
    if p is None:
        logger.warning(
            "[renewable-floor] Variable 'Generator-p' not found in linopy model. "
            "Available: %s — skipped.",
            list(lm.variables),
        )
        return

    # Identify the generator-axis dimension (last non-snapshot dim)
    gen_dim = None
    for dim in p.dims:
        if dim != "snapshot" and "snapshot" not in dim.lower():
            gen_dim = dim
            break
    if gen_dim is None:
        logger.warning("[renewable-floor] Could not identify generator dimension in %s — skipped.", p.dims)
        return

    # Filter to generators that actually appear in this variable's coordinates
    valid_coords = list(p.coords[gen_dim].values)
    renewable_in_model = [g for g in renewable_idx if g in valid_coords]
    all_in_model = valid_coords  # all generators present in the LP variable

    if not renewable_in_model:
        logger.warning("[renewable-floor] None of the renewable generators appear in the LP variable — skipped.")
        return

    logger.info(
        "[renewable-floor] Applying %.0f%% floor — %d/%d generators classified renewable.",
        floor_pct, len(renewable_in_model), len(all_in_model),
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
