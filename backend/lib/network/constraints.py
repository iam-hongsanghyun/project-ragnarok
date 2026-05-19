from __future__ import annotations

from typing import Any

import pypsa

from ..utils.coerce import number, put_if_present, text
from ..utils.workbook import workbook_rows


def add_global_constraints(
    network: pypsa.Network,
    model: dict[str, list[dict[str, Any]]],
    period_factor: float,
    notes: list[str],
) -> None:
    """Add GlobalConstraint rows from the workbook.

    Only `name` and `type` are required (PyPSA cannot resolve a global
    constraint without them). Everything else passes through only when the
    user provided a value.

    For `primary_energy` and `operational_limit` constraint types, the
    `constant` is scaled by `period_factor` so a daily/hourly snapshot
    selection has the proportionally-correct annual cap.
    """
    for row in workbook_rows(model, "global_constraints"):
        name = text(row.get("name"))
        constraint_type = text(row.get("type"))
        if not name:
            notes.append("A global_constraint row has no name — skipped.")
            continue
        if not constraint_type:
            notes.append(f"GlobalConstraint '{name}' has no type — skipped.")
            continue
        kwargs: dict[str, Any] = {"type": constraint_type}
        # `constant` is scaled by period_factor for energy/operational caps so
        # a partial-year run gets a proportional cap.
        if row.get("constant") not in (None, ""):
            scale = period_factor if constraint_type in {"primary_energy", "operational_limit"} else 1.0
            kwargs["constant"] = number(row.get("constant")) * scale
        put_if_present(kwargs, row, "sense", coerce=text)
        put_if_present(kwargs, row, "carrier_attribute", coerce=text)
        put_if_present(kwargs, row, "investment_period")
        network.add("GlobalConstraint", name, **kwargs)
