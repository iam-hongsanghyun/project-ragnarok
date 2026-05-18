from __future__ import annotations

from typing import Any

import pandas as pd
import pypsa

from ...constants import generator_color
from ...utils.series import safe_series, weighted_sum
from ...utils.coerce import text


def build_generator_details(
    network: pypsa.Network,
    dispatch_frame: pd.DataFrame,
    generator_weights: pd.Series,
    emissions_factors: dict[str, float] | None = None,
    currency: str = "$",
) -> dict[str, Any]:
    if emissions_factors is None:
        emissions_factors = (
            network.carriers["co2_emissions"].to_dict()
            if "co2_emissions" in network.carriers.columns
            else {}
        )
    details: dict[str, Any] = {}
    for generator in network.generators.index:
        dispatch = safe_series(dispatch_frame, generator)
        positive = dispatch.clip(lower=0.0)
        carrier = text(network.generators.at[generator, "carrier"], "Other")
        bus = text(network.generators.at[generator, "bus"])
        p_nom = float(network.generators.at[generator, "p_nom"]) if "p_nom" in network.generators.columns else 0.0
        availability = safe_series(network.generators_t.p_max_pu, generator) * p_nom
        energy = weighted_sum(positive, generator_weights)
        mc = float(network.generators.at[generator, "marginal_cost"]) if "marginal_cost" in network.generators.columns else 0.0
        emissions = weighted_sum(positive * emissions_factors.get(carrier, 0.0), generator_weights)
        weight_val = float(generator_weights.iloc[0]) if len(generator_weights) else 1.0

        output_s, emissions_s, available_s, curtailment_s = [], [], [], []
        for snapshot in network.snapshots:
            output = float(dispatch.loc[snapshot])
            avail = max(float(availability.loc[snapshot]) if snapshot in availability.index else output, 0.0)
            ts = pd.Timestamp(snapshot)
            label, stamp = ts.strftime("%H:%M"), ts.isoformat()
            output_s.append({"label": label, "timestamp": stamp, "output": output})
            emissions_s.append({"label": label, "timestamp": stamp, "emissions": max(output, 0.0) * emissions_factors.get(carrier, 0.0)})
            available_s.append({"label": label, "timestamp": stamp, "available": avail})
            curtailment_s.append({"label": label, "timestamp": stamp, "curtailment": max(avail - max(output, 0.0), 0.0)})

        details[generator] = {
            "name": generator, "carrier": carrier, "color": generator_color(network, generator), "bus": bus,
            "summary": [
                {"label": "Energy", "value": f"{round(energy):,} MWh", "detail": f"{weight_val:g} h weighting applied"},
                {"label": "Operating cost", "value": f"{round(energy * mc):,} {currency}", "detail": f"{mc:.1f} {currency}/MWh marginal cost"},
                {"label": "Emissions", "value": f"{round(emissions):,} tCO2e", "detail": f"{emissions_factors.get(carrier, 0.0):.2f} t/MWh carrier factor"},
            ],
            "outputSeries": output_s,
            "emissionsSeries": emissions_s,
            "availableSeries": available_s,
            "curtailmentSeries": curtailment_s,
        }
    return details
