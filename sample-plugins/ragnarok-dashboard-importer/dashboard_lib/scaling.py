"""Load scaling to match a target annual energy (TWh)."""
from __future__ import annotations

import pypsa


def scale_load(network: pypsa.Network, target_load_twh: float) -> None:
    """Scale the load time series so total annual energy equals *target_load_twh*.

    If ``target_load_twh`` is ``0`` (or any non-positive value), no scaling is
    applied and the imported profile is used as-is — useful when the dashboard
    ``load`` cell is left blank to mean "keep the original profile".

    Algorithm:
      ``scale_factor = (target_load_twh × 10⁶) / Σ(loads_t.p_set)``
      ``loads_t.p_set *= scale_factor``

    Args:
        network: PyPSA Network to modify in place.
        target_load_twh: Target annual energy in TWh.  ``0`` (or empty in the
            dashboard) means "do not scale".
    """
    sum_mwh = network.loads_t.p_set.sum().sum()
    original_twh = sum_mwh / 1e6

    if target_load_twh <= 0:
        print(
            f"  Load scaling: skipped (load cell empty or 0) — "
            f"using original profile ({original_twh:.1f} TWh)"
        )
        return

    scale_factor = target_load_twh * 1e6 / sum_mwh
    network.loads_t.p_set = network.loads_t.p_set * scale_factor

    print(
        f"  Load scaled by {scale_factor:.4f}  "
        f"({original_twh:.1f} TWh → {target_load_twh:.1f} TWh)"
    )
