from __future__ import annotations

from typing import Any

import pypsa

from ..utils.coerce import bool_value, number, put_if_present, text
from ..utils.workbook import workbook_rows


def add_lines(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    notes: list[str],
) -> None:
    """Add Line components. Every row with a non-empty `name` and resolvable
    bus0/bus1 is imported. No numeric defaults are fabricated; missing
    columns fall back to PyPSA's own component defaults."""
    for row in workbook_rows(model, "lines"):
        name = text(row.get("name"))
        bus0 = text(row.get("bus0"))
        bus1 = text(row.get("bus1"))
        if not name:
            notes.append("A line row has no name — skipped.")
            continue
        if bus0 not in network.buses.index or bus1 not in network.buses.index:
            notes.append(f"Line '{name}' references non-existent bus(es) — skipped.")
            continue
        kwargs: dict[str, Any] = {"bus0": bus0, "bus1": bus1}
        for col in ("x", "r", "b", "g", "s_nom", "length", "s_max_pu", "v_ang_min", "v_ang_max"):
            put_if_present(kwargs, row, col, coerce=number)
        put_if_present(kwargs, row, "num_parallel", coerce=lambda v: max(1, int(number(v, 1.0))))
        put_if_present(kwargs, row, "type", coerce=text)
        network.add("Line", name, **kwargs)


def add_links(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    notes: list[str],
) -> None:
    """Add Link components, including multi-port (bus2, bus3) sector-coupling links."""
    for row in workbook_rows(model, "links"):
        name = text(row.get("name"))
        bus0 = text(row.get("bus0"))
        bus1 = text(row.get("bus1"))
        if not name:
            notes.append("A link row has no name — skipped.")
            continue
        if bus0 not in network.buses.index or bus1 not in network.buses.index:
            notes.append(f"Link '{name}' references non-existent bus(es) — skipped.")
            continue
        carrier = text(row.get("carrier"))
        if carrier and carrier not in network.carriers.index:
            network.add("Carrier", carrier, co2_emissions=0.0)

        kwargs: dict[str, Any] = {"bus0": bus0, "bus1": bus1}
        if carrier:
            kwargs["carrier"] = carrier
        for col in (
            "p_nom", "p_min_pu", "p_max_pu", "efficiency", "marginal_cost", "capital_cost",
        ):
            put_if_present(kwargs, row, col, coerce=number)

        # Multi-output ports (sector coupling: CHP, co-generation, etc.)
        for suffix in ("2", "3"):
            b = text(row.get(f"bus{suffix}"))
            if b and b in network.buses.index:
                kwargs[f"bus{suffix}"] = b
                put_if_present(kwargs, row, f"efficiency{suffix}", coerce=number)

        # Optional capacity optimisation
        if bool_value(row.get("p_nom_extendable")):
            kwargs["p_nom_extendable"] = True
            p_nom_max = row.get("p_nom_max")
            if p_nom_max not in (None, "", "inf"):
                kwargs["p_nom_max"] = number(p_nom_max, float("inf"))

        network.add("Link", name, **kwargs)


def add_transformers(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    notes: list[str],
) -> None:
    for row in workbook_rows(model, "transformers"):
        name = text(row.get("name"))
        bus0 = text(row.get("bus0"))
        bus1 = text(row.get("bus1"))
        if not name:
            notes.append("A transformer row has no name — skipped.")
            continue
        if bus0 not in network.buses.index or bus1 not in network.buses.index:
            notes.append(f"Transformer '{name}' references non-existent bus(es) — skipped.")
            continue
        kwargs: dict[str, Any] = {"bus0": bus0, "bus1": bus1}
        for col in (
            "x", "r", "g", "b", "s_nom", "tap_ratio", "phase_shift", "s_max_pu",
        ):
            put_if_present(kwargs, row, col, coerce=number)
        put_if_present(kwargs, row, "tap_side", coerce=lambda v: int(number(v, 0.0)))
        put_if_present(kwargs, row, "type", coerce=text)
        put_if_present(kwargs, row, "model", coerce=text)
        network.add("Transformer", name, **kwargs)


def add_shunt_impedances(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    notes: list[str],
) -> None:
    for row in workbook_rows(model, "shunt_impedances"):
        name = text(row.get("name"))
        bus = text(row.get("bus"))
        if not name:
            notes.append("A shunt_impedance row has no name — skipped.")
            continue
        if bus not in network.buses.index:
            notes.append(f"ShuntImpedance '{name}' references non-existent bus '{bus}' — skipped.")
            continue
        kwargs: dict[str, Any] = {"bus": bus}
        for col in ("g", "b", "sign"):
            put_if_present(kwargs, row, col, coerce=number)
        network.add("ShuntImpedance", name, **kwargs)
