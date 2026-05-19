from __future__ import annotations

from typing import Any

import pypsa

from ..utils.coerce import bool_value, number, put_if_present, text
from ..utils.workbook import workbook_rows


def add_processes(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    notes: list[str],
) -> None:
    """Add PyPSA Process components from the workbook 'processes' sheet.

    PyPSA Process uses rate0/rate1 (not efficiency) as the conversion
    coefficients:
      - rate0 = -1.0  →  bus0 is an input (withdrawal, e.g. fuel)
      - rate1 = η     →  bus1 is an output equal to η × |input|

    The user-facing column is 'efficiency' (more familiar); the backend
    maps it to rate1 automatically. Optional bus2/bus3 ports follow the
    same pattern (efficiency2 → rate2, etc.).
    """
    for row in workbook_rows(model, "processes"):
        name = text(row.get("name"))
        bus0 = text(row.get("bus0"))
        bus1 = text(row.get("bus1"))
        if not name:
            notes.append("A process row has no name — skipped.")
            continue
        if bus0 not in network.buses.index or bus1 not in network.buses.index:
            notes.append(f"Process '{name}' references non-existent bus(es) — skipped.")
            continue

        carrier = text(row.get("carrier"))
        if carrier and carrier not in network.carriers.index:
            network.add("Carrier", carrier, co2_emissions=0.0)

        kwargs: dict[str, Any] = {"bus0": bus0, "bus1": bus1, "rate0": -1.0}
        if carrier:
            kwargs["carrier"] = carrier
        # Map user-facing efficiency → PyPSA rate1
        if row.get("efficiency") not in (None, ""):
            kwargs["rate1"] = number(row.get("efficiency"))
        for col in ("p_nom", "p_min_pu", "p_max_pu", "marginal_cost", "capital_cost"):
            put_if_present(kwargs, row, col, coerce=number)

        # Optional extendable capacity
        if bool_value(row.get("p_nom_extendable")):
            kwargs["p_nom_extendable"] = True
            p_nom_max = row.get("p_nom_max")
            if p_nom_max not in (None, "", "inf"):
                kwargs["p_nom_max"] = number(p_nom_max, float("inf"))

        # Optional multi-output ports (e.g. CHP: bus2 = heat output)
        for suffix in ("2", "3"):
            b = text(row.get(f"bus{suffix}"))
            if b and b in network.buses.index:
                kwargs[f"bus{suffix}"] = b
                if row.get(f"efficiency{suffix}") not in (None, ""):
                    kwargs[f"rate{suffix}"] = number(row.get(f"efficiency{suffix}"))

        network.add("Process", name, **kwargs)
