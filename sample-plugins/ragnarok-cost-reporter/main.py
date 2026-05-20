"""
ragnarok-cost-reporter — analytics-pack sample plugin
=====================================================
Stage : post-solve
Hook  : analyse(network, results, scenario, options) -> dict

Called after network.optimize() completes.  Returns a dict of extra metrics
that is stored in run results under pluginAnalytics["ragnarok-cost-reporter"]
and rendered in the frontend using the ui hints declared in module.json.

Computed metrics (controlled by moduleConfig flags):
  total_opex            — total operating expenditure (always included)
  total_capex           — annualised CAPEX  (include_capex=True, default)
  total_cost            — total_opex + total_capex (or total_opex only)
  total_energy_mwh      — total energy served (MWh, weighted by snapshotWeight)
  lcoe_per_mwh          — levelised cost of energy
  avg_nodal_price       — mean LMP across all buses and snapshots
  max_nodal_price       — peak LMP
  min_nodal_price       — floor LMP
  carrier_cost_breakdown — fuel cost per carrier  (include_carrier_breakdown=True)

Config (module.json):
  include_capex              (bool, default True)
  include_carrier_breakdown  (bool, default True)
"""
from __future__ import annotations

import logging
from typing import Any

import pypsa

logger = logging.getLogger(__name__)


def analyse(
    network: pypsa.Network,
    results: dict[str, Any],
    scenario: dict[str, Any],
    options: dict[str, Any],
) -> dict[str, Any]:
    """Compute extended cost and price analytics on the solved network.

    Args:
        network:  Solved pypsa.Network.
        results:  Core results already assembled by Ragnarok (read-only).
        scenario: Scenario parameters.
        options:  Run options; reads ``snapshotWeight``.
                  ``options["moduleConfig"]`` is injected by the host and
                  contains this module's own config values.

    Returns:
        Dict of analytics metrics (see module docstring).
    """
    module_config = options.get("moduleConfig", {})
    include_capex     = bool(module_config.get("include_capex",             True))
    include_breakdown = bool(module_config.get("include_carrier_breakdown", True))

    snapshot_weight = float(options.get("snapshotWeight", 1.0))
    out: dict[str, Any] = {}

    # ── Operational (and optional capital) expenditure ────────────────────────
    try:
        stats = network.statistics
        oc = stats.operational_expenditure(aggregate_time=True)
        out["total_opex"] = round(float(oc.sum()) if not oc.empty else 0.0, 2)

        if include_capex:
            ic = stats.capital_expenditure(aggregate_time=True)
            out["total_capex"] = round(float(ic.sum()) if not ic.empty else 0.0, 2)
            out["total_cost"]  = round(out["total_opex"] + out["total_capex"], 2)
        else:
            out["total_cost"] = out["total_opex"]
    except Exception as exc:  # noqa: BLE001
        logger.warning("[cost-reporter] statistics API failed: %s", exc)

    # ── Total energy served ───────────────────────────────────────────────────
    # Prefer the actual optimised dispatch (loads_t.p); fall back to the
    # exogenous set-point (loads_t.p_set) for fixed-load models.
    try:
        load_p = network.loads_t.p
        if load_p.empty:
            load_p = network.loads_t.p_set
        if not load_p.empty:
            out["total_energy_mwh"] = round(
                float(load_p.sum().sum()) * snapshot_weight, 1
            )
    except Exception as exc:  # noqa: BLE001
        logger.warning("[cost-reporter] load energy failed: %s", exc)

    # ── LCOE ──────────────────────────────────────────────────────────────────
    if "total_cost" in out and out.get("total_energy_mwh", 0) > 0:
        out["lcoe_per_mwh"] = round(out["total_cost"] / out["total_energy_mwh"], 4)

    # ── Nodal (marginal) prices ───────────────────────────────────────────────
    try:
        lmp = network.buses_t.marginal_price
        if not lmp.empty:
            out["avg_nodal_price"] = round(float(lmp.mean().mean()), 4)
            out["max_nodal_price"] = round(float(lmp.max().max()), 4)
            out["min_nodal_price"] = round(float(lmp.min().min()), 4)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[cost-reporter] nodal prices failed: %s", exc)

    # ── Per-carrier fuel cost breakdown ───────────────────────────────────────
    if include_breakdown:
        try:
            gens    = network.generators
            gen_p   = network.generators_t.p
            weights = (
                network.snapshot_weightings["generators"]
                .reindex(network.snapshots)
                .fillna(snapshot_weight)
            )
            if not gens.empty and not gen_p.empty:
                carrier_cost: dict[str, float] = {}
                for carrier, grp in gens.groupby("carrier"):
                    cols = [c for c in grp.index if c in gen_p.columns]
                    if not cols:
                        continue
                    mc   = grp.loc[cols, "marginal_cost"].fillna(0.0)
                    cost = float(
                        (gen_p[cols].multiply(mc, axis=1))
                        .multiply(weights, axis=0)
                        .sum().sum()
                    )
                    carrier_cost[str(carrier)] = round(cost, 2)
                if carrier_cost:
                    out["carrier_cost_breakdown"] = carrier_cost
        except Exception as exc:  # noqa: BLE001
            logger.warning("[cost-reporter] carrier cost failed: %s", exc)

    logger.info(
        "[cost-reporter] total_cost=%s  lcoe=%s  avg_lmp=%s  capex=%s  breakdown=%s",
        out.get("total_cost"), out.get("lcoe_per_mwh"), out.get("avg_nodal_price"),
        include_capex, include_breakdown,
    )
    return out
