"""Network topology transformations.

Public entry point :func:`apply_topology` dispatches on
``settings.grid_mode``:

================================  ==========================================
``grid_mode``                     Action
================================  ==========================================
``single``                        :func:`collapse_to_single_bus`
``line_to_link``                  :func:`line_to_link`
``merge_line_transformer``        :func:`merge_line_transformer`
``as-is`` (or anything else)      Imported topology kept unchanged.
================================  ==========================================

For energy-balance / dispatch studies (no power-flow analysis) the two new
modes replace the Kirchhoff Voltage Law constraints — whose tiny
susceptance coefficients (``b · z_base``, ~1e-3) cause HiGHS dual-simplex
blow-up on the meshed Korean grid — with a transport network of
bidirectional ``Link`` components.
"""
from __future__ import annotations

import pandas as pd
import pypsa

# Forward-only typing to avoid a cycle with :mod:`lib.settings`
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lib.settings import Settings


def collapse_to_single_bus(network: pypsa.Network, bus_name: str) -> None:
    """Collapse the network to a single bus, removing all lines and transformers.

    All generators and storage units are reassigned to *bus_name*.
    All loads are **aggregated** into a single ``load_total`` object:

    - Time-series ``p_set`` columns are summed into one column.
    - Static ``p_set`` scalars are summed into one scalar.

    Lines, transformers, and original buses are removed.

    Args:
        network: PyPSA Network to modify in place.
        bus_name: Name of the single aggregated bus (from dashboard ``Single_bus`` row).
    """
    LOAD_NAME = "load_total"

    # 1. Add the single aggregated bus
    network.add("Bus", bus_name, carrier="AC")

    # 2. Aggregate all loads into one ──────────────────────────────────────
    if not network.loads_t.p_set.empty:
        agg_p_set_t = network.loads_t.p_set.sum(axis=1)   # Series: snapshot → MW
    else:
        agg_p_set_t = None

    agg_p_set_scalar = (
        float(network.loads["p_set"].sum())
        if "p_set" in network.loads.columns
        else 0.0
    )

    network.remove("Load", network.loads.index)
    network.add(
        "Load",
        LOAD_NAME,
        bus=bus_name,
        carrier="load",
        p_set=agg_p_set_scalar if agg_p_set_t is None else 0.0,
    )

    if agg_p_set_t is not None:
        network.loads_t.p_set = pd.DataFrame(
            {LOAD_NAME: agg_p_set_t}, index=network.snapshots
        )

    # 3. Reassign generators and storage units
    network.generators["bus"] = bus_name
    if not network.storage_units.empty:
        network.storage_units["bus"] = bus_name

    # 4. Remove transmission
    if not network.lines.empty:
        network.remove("Line", network.lines.index)
    if not network.transformers.empty:
        network.remove("Transformer", network.transformers.index)

    # 5. Remove all original buses (now unreferenced)
    original = network.buses.index[network.buses.index != bus_name]
    if len(original):
        network.remove("Bus", original)

    total_mw = agg_p_set_scalar if agg_p_set_t is None else float(agg_p_set_t.mean())
    print(
        f"  Topology: single bus '{bus_name}'  "
        f"({len(network.generators)} generators, 1 load  "
        f"[avg {total_mw:.1f} MW])"
    )


def _validate_loss(link_loss: float) -> None:
    if not (0.0 <= link_loss < 1.0):
        raise ValueError(f"link_loss must be in [0, 1) — got {link_loss!r}")


def _add_bidirectional_link(
    network: pypsa.Network,
    bus0: str,
    bus1: str,
    p_nom: float,
    efficiency: float,
) -> None:
    """Add one bidirectional Link with deterministic name ``link_<a>_<b>``."""
    a, b = sorted((bus0, bus1))
    network.add(
        "Link",
        f"link_{a}_{b}",
        bus0=a,
        bus1=b,
        p_nom=p_nom,
        efficiency=efficiency,
        p_min_pu=-1.0,
    )


def line_to_link(network: pypsa.Network, link_loss: float) -> None:
    """Replace every line and transformer with a bidirectional ``Link``.

    Lines become **lossy** (``η = 1 − link_loss``) since they are real
    transmission distance; transformers become **lossless** (``η = 1.0``)
    because they connect different voltage buses at the same physical
    substation and applying a transmission-style loss would double-count.

    All 193 buses are kept.  Parallel lines + transformers between the same
    unordered ``{bus0, bus1}`` pair are **deduplicated** — capacities are
    summed and the worst (lowest) efficiency wins.

    Algorithm:
        $$p^{\\mathrm{nom}}_{\\{a,b\\}} = \\sum_{\\ell \\,:\\, \\{a,b\\}}
          s^{\\mathrm{nom}}_\\ell$$
        $$\\eta_{\\{a,b\\}} = \\min_{\\ell \\,:\\, \\{a,b\\}} \\eta_\\ell$$

        ASCII:
          p_nom_{a,b} = sum_{ℓ in lines+trafos with {bus0,bus1}={a,b}} s_nom_ℓ
          η_{a,b}     = min over those branches of their per-branch η

    Args:
        network:   PyPSA Network to modify in place.
        link_loss: Fractional loss applied to line-derived links
                   (e.g. ``0.05`` → 5 %).  Must satisfy ``0 ≤ link_loss < 1``.

    Raises:
        ValueError: If ``link_loss`` is outside ``[0, 1)``.
    """
    _validate_loss(link_loss)
    line_eff = 1.0 - link_loss
    trafo_eff = 1.0

    edges: dict[frozenset[str], tuple[float, float]] = {}  # pair → (p_nom, η)

    def _accumulate(df: pd.DataFrame, edge_eff: float) -> int:
        if df.empty:
            return 0
        n = 0
        for _, row in df.iterrows():
            a, b = str(row["bus0"]), str(row["bus1"])
            if a == b:
                continue
            pair = frozenset((a, b))
            cap = float(row.get("s_nom", 0.0) or 0.0)
            prev_p, prev_eta = edges.get(pair, (0.0, 1.0))
            edges[pair] = (prev_p + cap, min(prev_eta, edge_eff))
            n += 1
        return n

    n_lines = _accumulate(network.lines, line_eff)
    n_trafos = _accumulate(network.transformers, trafo_eff)

    if not network.lines.empty:
        network.remove("Line", network.lines.index)
    if not network.transformers.empty:
        network.remove("Transformer", network.transformers.index)

    for pair, (p_nom, eta) in edges.items():
        a, b = sorted(pair)
        _add_bidirectional_link(network, a, b, p_nom, eta)

    print(
        f"  Topology: line_to_link  "
        f"({n_lines} lines @ η={line_eff:.3f} + "
        f"{n_trafos} transformers @ η=1.000 → "
        f"{len(edges)} unique links)"
    )


def merge_line_transformer(network: pypsa.Network, link_loss: float) -> None:
    """Merge transformer-connected buses into substations, then turn lines into Links.

    Transformer endpoints are treated as the **same physical location**
    (different voltage levels of one substation).  Buses linked through any
    chain of transformers are unioned into a substation group; one canonical
    bus per group survives, the rest are dropped.  All component bus
    references (generators, loads, storage units, stores, lines, links) are
    rewritten to the canonical bus.

    Lines that become self-loops after the merge are discarded; lines that
    end up parallel are summed.  The remaining unique pairs become
    bidirectional ``Link`` components with ``η = 1 − link_loss``.

    Canonical-bus selection: the bus with the **highest** ``v_nom`` in the
    group; ties broken lexicographically by name.

    Algorithm:
        groups       = connected_components(G_trafo)        # union-find
        canonical(g) = argmax_{b ∈ g}( v_nom(b), -name(b) )
        for component c:  c.bus_ref ← canonical(group(c.bus_ref))
        drop self-loop lines
        merge parallel lines: p_nom_{a,b} = Σ s_nom_ℓ
        η = 1 − link_loss

    Args:
        network:   PyPSA Network to modify in place.
        link_loss: Fractional loss applied to every resulting Link.
                   Must satisfy ``0 ≤ link_loss < 1``.

    Raises:
        ValueError: If ``link_loss`` is outside ``[0, 1)``.
    """
    _validate_loss(link_loss)
    eta = 1.0 - link_loss

    n_buses_before = len(network.buses)
    n_lines_before = len(network.lines)
    n_trafos_before = len(network.transformers)

    # 1. Union-find: group every bus joined through any chain of transformers
    parent: dict[str, str] = {b: b for b in network.buses.index}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for _, row in network.transformers.iterrows():
        union(str(row["bus0"]), str(row["bus1"]))

    # 2. Canonical bus per group: max v_nom, then lex(name)
    v_nom = (
        network.buses["v_nom"]
        if "v_nom" in network.buses.columns
        else pd.Series(0.0, index=network.buses.index)
    )
    groups: dict[str, list[str]] = {}
    for b in network.buses.index:
        groups.setdefault(find(b), []).append(b)

    canonical: dict[str, str] = {}
    for members in groups.values():
        max_v = max(float(v_nom.get(m, 0.0)) for m in members)
        ties = [m for m in members if float(v_nom.get(m, 0.0)) == max_v]
        best = sorted(ties)[0]
        for m in members:
            canonical[m] = best

    # 3. Remap every component's bus references
    def _remap(df: pd.DataFrame, cols: list[str]) -> None:
        if df.empty:
            return
        for c in cols:
            if c in df.columns:
                df[c] = df[c].map(lambda x: canonical.get(str(x), str(x)))

    _remap(network.generators,    ["bus"])
    _remap(network.loads,         ["bus"])
    _remap(network.storage_units, ["bus"])
    _remap(network.stores,        ["bus"])
    _remap(network.lines,         ["bus0", "bus1"])
    _remap(network.links,         ["bus0", "bus1"])

    # 4. Drop transformers (now intra-substation)
    if not network.transformers.empty:
        network.remove("Transformer", network.transformers.index)

    # 5. Aggregate remaining lines into deduplicated unordered pairs
    edges: dict[frozenset[str], float] = {}
    for _, row in network.lines.iterrows():
        a, b = str(row["bus0"]), str(row["bus1"])
        if a == b:
            continue                       # self-loop after merge
        pair = frozenset((a, b))
        cap = float(row.get("s_nom", 0.0) or 0.0)
        edges[pair] = edges.get(pair, 0.0) + cap

    if not network.lines.empty:
        network.remove("Line", network.lines.index)

    # 6. Drop now-unused (non-canonical) buses
    keep = set(canonical.values())
    drop = [b for b in network.buses.index if b not in keep]
    if drop:
        network.remove("Bus", drop)

    # 7. Add the deduplicated, bidirectional Links
    for pair, p_nom in edges.items():
        a, b = sorted(pair)
        _add_bidirectional_link(network, a, b, p_nom, eta)

    print(
        f"  Topology: merge_line_transformer  "
        f"({n_buses_before} buses → {len(network.buses)} substations, "
        f"{n_lines_before} lines + {n_trafos_before} transformers → "
        f"{len(edges)} unique links @ η={eta:.3f})"
    )


def apply_topology(network: pypsa.Network, settings: "Settings") -> None:
    """Dispatch on ``settings.grid_mode`` and apply the matching transform.

    Recognised values:

    * ``single``                  → :func:`collapse_to_single_bus`
    * ``line_to_link``            → :func:`line_to_link`
    * ``merge_line_transformer``  → :func:`merge_line_transformer`
    * any other value (incl. ``as-is``) → no-op, prints the chosen mode.

    Args:
        network:  PyPSA Network to modify in place.
        settings: Parsed dashboard :class:`~lib.settings.Settings`.  This
            function reads ``grid_mode``, ``single_bus``, and ``link_loss``.
    """
    mode = settings.grid_mode
    if mode == "single":
        collapse_to_single_bus(network, settings.single_bus)
    elif mode == "line_to_link":
        line_to_link(network, settings.link_loss)
    elif mode == "merge_line_transformer":
        merge_line_transformer(network, settings.link_loss)
    else:
        print(f"  Topology: as-is  ({len(network.buses)} buses, "
              f"{len(network.lines)} lines, {len(network.transformers)} transformers)")


def drop_components_with_missing_buses(network: pypsa.Network) -> None:
    """Remove components that reference buses absent from the network.

    Checks generators, loads, storage units, lines, transformers, and links.
    Safe to call after any topology reduction (e.g. after
    :func:`collapse_to_single_bus`).

    Args:
        network: PyPSA Network to modify in place.
    """
    valid_buses = set(network.buses.index)
    removed_count = 0

    single_bus_components = [
        ("Generator", network.generators),
        ("Load", network.loads),
        ("StorageUnit", network.storage_units),
    ]

    for component_type, df in single_bus_components:
        if not df.empty and "bus" in df.columns:
            invalid = df.index[~df["bus"].isin(valid_buses)]
            if len(invalid):
                network.remove(component_type, invalid)
                removed_count += len(invalid)
                print(f"    Removed {len(invalid)} {component_type.lower()}(s) with missing buses")

    dual_bus_components = [
        ("Line", network.lines),
        ("Transformer", network.transformers),
        ("Link", network.links),
    ]

    for component_type, df in dual_bus_components:
        if not df.empty:
            invalid = df.index[
                ~df["bus0"].isin(valid_buses) | ~df["bus1"].isin(valid_buses)
            ]
            if len(invalid):
                network.remove(component_type, invalid)
                removed_count += len(invalid)
                print(f"    Removed {len(invalid)} {component_type.lower()}(s) with missing buses")

    if removed_count == 0:
        print("  No components with missing buses found")
