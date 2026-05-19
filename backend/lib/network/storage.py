from __future__ import annotations

from typing import Any

import pypsa

from ..utils.annuity import annuity_factor
from ..utils.coerce import bool_value, number, put_if_present, text
from ..utils.workbook import apply_scaled_static_attributes, workbook_rows


def add_stores(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    period_factor: float,
    notes: list[str],
) -> None:
    """Add Store components. Only `name` and a resolvable `bus` are required;
    other columns pass through only when present (no fabricated defaults)."""
    for row in workbook_rows(model, "stores"):
        name = text(row.get("name"))
        bus = text(row.get("bus"))
        if not name:
            notes.append("A store row has no name — skipped.")
            continue
        if bus not in network.buses.index:
            notes.append(f"Store '{name}' references non-existent bus '{bus}' — skipped.")
            continue
        carrier = text(row.get("carrier"))
        if carrier and carrier not in network.carriers.index:
            network.add("Carrier", carrier, co2_emissions=0.0)
        store_kwargs: dict[str, Any] = {"bus": bus}
        if carrier:
            store_kwargs["carrier"] = carrier
        for col in (
            "e_nom", "e_nom_min", "e_nom_max", "e_initial", "e_min_pu", "e_max_pu",
            "e_cyclic_per_period", "standing_loss", "marginal_cost", "capital_cost",
        ):
            put_if_present(store_kwargs, row, col, coerce=number)
        put_if_present(store_kwargs, row, "e_nom_extendable", coerce=bool_value)
        put_if_present(store_kwargs, row, "e_cyclic", coerce=bool_value)
        network.add("Store", name, **store_kwargs)
        applied = apply_scaled_static_attributes(network.stores, name, row, period_factor)
        if applied:
            notes.append(f"Scaled {', '.join(applied)} for store {name} by period factor {period_factor:.2f}.")


def add_storage_units(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    period_factor: float,
    notes: list[str],
    discount_rate: float,
    currency: str = "$",
) -> None:
    """Add StorageUnit components. Only `name` and a resolvable `bus` are
    required; other columns pass through only when present."""
    for row in workbook_rows(model, "storage_units"):
        name = text(row.get("name"))
        bus = text(row.get("bus"))
        if not name:
            notes.append("A storage_unit row has no name — skipped.")
            continue
        if bus not in network.buses.index:
            notes.append(f"StorageUnit '{name}' references non-existent bus '{bus}' — skipped.")
            continue
        carrier = text(row.get("carrier"))
        if carrier and carrier not in network.carriers.index:
            network.add("Carrier", carrier, co2_emissions=0.0)

        extendable = bool_value(row.get("extendable"), False)
        raw_capital_cost = number(row.get("capital_cost"), 0.0)
        if extendable:
            lifetime = number(row.get("asset_lifetime"), 15.0)
            af = annuity_factor(discount_rate, lifetime)
            annualised_capital_cost = raw_capital_cost * af
            notes.append(
                f"StorageUnit '{name}' is extendable (lifetime={lifetime:.0f}yr, "
                f"AF={af:.4f}, annualised capex={annualised_capital_cost:.0f} {currency}/MW/yr)."
            )
        else:
            annualised_capital_cost = raw_capital_cost

        su_kwargs: dict[str, Any] = {
            "bus": bus,
            "p_nom_extendable": extendable,
            "capital_cost": annualised_capital_cost,
        }
        if carrier:
            su_kwargs["carrier"] = carrier
        for col in (
            "p_nom", "p_nom_min", "p_nom_max", "max_hours",
            "efficiency_store", "efficiency_dispatch",
            "state_of_charge_initial", "marginal_cost",
            "p_min_pu", "p_max_pu",
        ):
            put_if_present(su_kwargs, row, col, coerce=number)
        put_if_present(su_kwargs, row, "cyclic_state_of_charge", coerce=bool_value)
        network.add("StorageUnit", name, **su_kwargs)
        applied = apply_scaled_static_attributes(network.storage_units, name, row, period_factor)
        if applied:
            notes.append(f"Scaled {', '.join(applied)} for storage unit {name} by period factor {period_factor:.2f}.")
