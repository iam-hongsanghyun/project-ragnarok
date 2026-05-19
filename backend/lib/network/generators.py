from __future__ import annotations

from typing import Any

import pandas as pd
import pypsa

from ..config import load_system_defaults
from ..utils.annuity import annuity_factor
from ..utils.coerce import bool_value, number, text
from ..utils.workbook import apply_scaled_static_attributes, workbook_rows
from .buses import parse_ts_sheet


def _carrier_emissions(network: pypsa.Network, carrier: str) -> float:
    if carrier in network.carriers.index and "co2_emissions" in network.carriers.columns:
        return float(network.carriers.at[carrier, "co2_emissions"])
    return 0.0


def add_generators(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    snapshots: pd.Index,
    period_factor: float,
    carbon_price: float,
    notes: list[str],
    discount_rate: float,
    *,
    snapshot_start: int = 0,
    snapshot_window: int | None = None,
    step: int = 1,
    force_lp: bool = False,
    currency: str = "$",
) -> None:
    generators = workbook_rows(model, "generators")
    if not generators:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Workbook has no generators.")

    # Load time-series override sheets — downsample by step to match snapshot index
    ts_p_max_pu = parse_ts_sheet(
        model,
        "generators-p_max_pu",
        snapshots,
        snapshot_start=snapshot_start,
        snapshot_window=snapshot_window,
        step=step,
    )
    ts_p_min_pu = parse_ts_sheet(
        model,
        "generators-p_min_pu",
        snapshots,
        snapshot_start=snapshot_start,
        snapshot_window=snapshot_window,
        step=step,
    )

    for row in generators:
        name = text(row.get("name"))
        bus = text(row.get("bus"))
        carrier = text(row.get("carrier"))
        if not name or bus not in network.buses.index:
            continue
        # A blank carrier is allowed — the generator still participates in
        # dispatch. Its emissions factor is 0 unless a carrier with a
        # co2_emissions value is declared and referenced.
        p_nom = number(row.get("p_nom"), 0.0)
        marginal_cost = (
            number(row.get("marginal_cost"), 0.0)
            + carbon_price * (_carrier_emissions(network, carrier) if carrier else 0.0)
        )
        p_max_pu_static = number(row.get("p_max_pu"), 1.0)
        p_min_pu_static = number(row.get("p_min_pu"), 0.0)
        extendable = bool_value(row.get("extendable"), False)
        # committable=True and p_nom_extendable=True are mutually exclusive in PyPSA
        committable = bool_value(row.get("committable"), False) and not force_lp
        if committable and extendable:
            notes.append(
                f"Generator '{name}': committable=True overrides extendable=True "
                f"(PyPSA MIP restriction — capacity will not be optimised)."
            )
            extendable = False
        raw_capital_cost = number(row.get("capital_cost"), 0.0)
        if extendable:
            lifetime = number(row.get("asset_lifetime"), 20.0)
            af = annuity_factor(discount_rate, lifetime)
            annualised_capital_cost = raw_capital_cost * af
            notes.append(
                f"Generator '{name}' is extendable (lifetime={lifetime:.0f}yr, "
                f"AF={af:.4f}, annualised capex={annualised_capital_cost:.0f} {currency}/MW/yr)."
            )
        else:
            annualised_capital_cost = 0.0
        gen_kwargs: dict[str, Any] = dict(
            bus=bus,
            control=text(row.get("control"), "PQ"),
            p_nom=p_nom,
            p_nom_min=0.0,
            p_min_pu=p_min_pu_static,
            p_max_pu=p_max_pu_static,
            marginal_cost=marginal_cost,
            capital_cost=annualised_capital_cost,
            p_nom_extendable=extendable,
            committable=committable,
        )
        if carrier:
            gen_kwargs["carrier"] = carrier
        # Unit-commitment attributes — only relevant when committable=True
        if committable:
            for uc_attr in ("min_up_time", "min_down_time", "start_up_cost", "shut_down_cost"):
                val = number(row.get(uc_attr), 0.0)
                if val > 0:
                    gen_kwargs[uc_attr] = val
        network.add("Generator", name, **gen_kwargs)
        color = text(row.get("color"))
        if color:
            network.generators.at[name, "color"] = color
        applied = apply_scaled_static_attributes(network.generators, name, row, period_factor)
        if applied:
            notes.append(f"Scaled {', '.join(applied)} for generator {name} by period factor {period_factor:.2f}.")

        # Assign time-series p_max_pu from workbook sheet if present; else no override (static used)
        if ts_p_max_pu and name in ts_p_max_pu:
            network.generators_t.p_max_pu.loc[:, name] = ts_p_max_pu[name]
        # Assign time-series p_min_pu if present
        if ts_p_min_pu and name in ts_p_min_pu:
            network.generators_t.p_min_pu.loc[:, name] = ts_p_min_pu[name]


def add_load_shedding(
    network: pypsa.Network,
    load_totals: dict[str, float],
    notes: list[str],
    enable_load_shedding: bool = False,
    load_shedding_cost: float | None = None,
    currency: str = "$",
) -> None:
    """Add per-bus load-shedding generators when ``enable_load_shedding`` is True.

    Load shedding represents the value of lost load (VOLL): a high-priced
    "generator" that allows the model to leave demand unserved at a known
    penalty rather than infeasibility. Pricing is supplied by the user via
    ``load_shedding_cost`` in the currency configured in Settings.

    When *enable_load_shedding* is False, no shedding generators are added —
    any supply shortfall will surface as a solver infeasibility error.
    """
    if not enable_load_shedding:
        notes.append("Load shedding disabled — infeasibility will surface as a solver error.")
        return

    cfg = load_system_defaults()
    ls_cfg = cfg["load_shedding"]
    cost = float(load_shedding_cost) if load_shedding_cost is not None else float(ls_cfg["marginal_cost"])

    # Shedding capacity is uncapped: the solver must be free to curtail the
    # full bus demand at any snapshot. We size to the system-wide peak demand
    # across all snapshots (covers both static p_set and time-series loads).
    try:
        peak_total = float(network.loads_t.p_set.sum(axis=1).max())
    except Exception:
        peak_total = 0.0
    static_total = float(sum(load_totals.values())) if load_totals else 0.0
    p_nom_uncapped = max(peak_total, static_total, 1.0)
    for bus in network.buses.index:
        shed_name = f"load_shedding_{bus}"
        network.add(
            "Generator",
            shed_name,
            bus=bus,
            carrier=ls_cfg["carrier"],
            p_nom=p_nom_uncapped,
            marginal_cost=cost,
        )
        network.generators_t.p_max_pu.loc[:, shed_name] = 1.0
    notes.append(
        f"Load shedding generators added for {len(network.buses)} bus(es) "
        f"at {cost:.0f} {currency}/MWh (value of lost load)."
    )
