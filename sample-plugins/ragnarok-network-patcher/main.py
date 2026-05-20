"""
ragnarok-network-patcher — data-manipulator sample plugin
=========================================================
Stage : post-build
Hook  : manipulate(network, scenario, options) -> None

Called after build_network() and before optimize().  Receives the fully
constructed pypsa.Network and modifies it in-place.  Return value is ignored.

This sample applies two optional patches (each toggled via moduleConfig):

  1. fix_negative_p_nom_min (default: True)
     Clamps any generator with p_nom_min < 0 to 0.  Negative p_nom_min is
     physically invalid for dispatchable units and causes solver infeasibility.

  2. warn_zero_capacity (default: True)
     Logs any generator whose p_nom is 0 AND is not extendable.  These
     contribute nothing to the model and are often data-entry errors.

Both patches are silent when no issues are found.
"""
from __future__ import annotations

import logging
from typing import Any

import pypsa

logger = logging.getLogger(__name__)


def manipulate(
    network: pypsa.Network,
    scenario: dict[str, Any],
    options: dict[str, Any],
) -> None:
    """Inspect and patch the built network in-place.

    Args:
        network:  Fully constructed pypsa.Network.
        scenario: Scenario parameters.
        options:  Run options; ``options["moduleConfig"]`` is injected by the
                  host and contains this module's own config values.
    """
    module_config = options.get("moduleConfig", {})
    fix_neg   = bool(module_config.get("fix_negative_p_nom_min", True))
    warn_zero = bool(module_config.get("warn_zero_capacity",     True))

    n = network

    # ── Summary ───────────────────────────────────────────────────────────────
    logger.info(
        "[network-patcher] %d buses  %d generators  %d loads  "
        "%d lines  %d links  %d storage_units  %d snapshots",
        len(n.buses), len(n.generators), len(n.loads),
        len(n.lines), len(n.links), len(n.storage_units), len(n.snapshots),
    )

    if n.generators.empty:
        return

    # ── Patch 1: clamp negative p_nom_min to 0 ────────────────────────────────
    if fix_neg and "p_nom_min" in n.generators.columns:
        neg = n.generators.index[n.generators["p_nom_min"] < 0]
        if len(neg):
            n.generators.loc[neg, "p_nom_min"] = 0.0
            logger.warning(
                "[network-patcher] Clamped p_nom_min → 0 on %d generator(s): %s",
                len(neg), neg.tolist(),
            )
        else:
            logger.info("[network-patcher] p_nom_min fix: no negative values found.")
    elif not fix_neg:
        logger.info("[network-patcher] p_nom_min fix: disabled via config.")

    # ── Patch 2: warn on zero-capacity non-extendable generators ─────────────
    if warn_zero:
        zero_cap = n.generators.index[
            (n.generators["p_nom"] == 0)
            & ~n.generators.get("p_nom_extendable", False).astype(bool)
        ]
        if len(zero_cap):
            logger.warning(
                "[network-patcher] %d generator(s) have p_nom=0 and are not extendable "
                "(they contribute nothing): %s",
                len(zero_cap), zero_cap.tolist(),
            )
        else:
            logger.info("[network-patcher] zero-capacity check: all generators look fine.")
    else:
        logger.info("[network-patcher] zero-capacity check: disabled via config.")
