"""Aggregate buses into regions and re-deduplicate the inter-region Links.

Designed to run **after** :func:`~lib.topology.apply_topology` so the
network already carries transmission as ``Link`` components.  This module
does not touch ``Line`` or ``Transformer`` components — if any remain after
``apply_topology`` they will be aggregated as-is along with the links.

How regions are determined
--------------------------
Each bus carries a province in either ``Province`` (capital) or ``province``
(lowercase) column.  The ``settings.region_column`` value picks the granularity:

* ``"province"`` — region = the *short* code from the ``province_mapping``
  sheet (e.g. ``"강원"``).  If the province has no short-code row, the
  official name is used verbatim.
* ``"group1"`` / ``"group2"`` / ``"group3"`` / ``"singlenode"`` (or any
  column present in ``province_mapping``) — region = the value of that
  column for the bus's province.

Effect on the network
---------------------
* One canonical bus per region; old buses are dropped.
* All component ``bus`` / ``bus0`` / ``bus1`` references are rewritten to
  the region name.
* Each unique unordered ``{bus0, bus1}`` link pair survives once.  Parallel
  links collapse via ``p_nom`` sum and ``efficiency`` min.
* Intra-region links (``bus0 == bus1`` after the rewrite) are dropped —
  flow inside a region is free.
* Loads remain individual; they just point at the new region bus.  PyPSA
  sums them at the bus's nodal balance.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import pandas as pd
import pypsa

if TYPE_CHECKING:
    from lib.settings import Dashboard


# Columns that always live on a province_mapping row (case-insensitive).
_RESERVED_MAPPING_COLS = {"short", "official"}

# Default aggregation rules used when no aggregation_by_region sheet is present.
# These reproduce the previous hardcoded behaviour.
_DEFAULT_LINK_RULES:  dict[str, str] = {"p_nom": "sum", "efficiency": "min", "p_min_pu": "min"}
_DEFAULT_BUS_RULES:   dict[str, str] = {"x": "mean", "y": "mean", "v_nom": "max"}
_DEFAULT_RULE = "ignore"


def _region_rule_lookup(
    rules_df: pd.DataFrame | None,
    component: str,
) -> tuple[dict[str, str], str]:
    """Return ``(attribute → rule, default_rule)`` for *component*.

    Falls back to built-in defaults when *rules_df* is ``None``.
    """
    if rules_df is None or rules_df.empty:
        if component == "links":
            return dict(_DEFAULT_LINK_RULES), _DEFAULT_RULE
        if component == "buses":
            return dict(_DEFAULT_BUS_RULES), _DEFAULT_RULE
        return {}, _DEFAULT_RULE

    comp_df = rules_df[rules_df["component"] == component.lower()]
    table: dict[str, str] = {
        str(a).strip(): str(r).strip()
        for a, r in zip(comp_df["attribute"], comp_df["rule"])
    }
    default = table.pop("others", _DEFAULT_RULE)
    return table, default


def _apply_region_rule(
    series: pd.Series,
    rule: str,
    region: str = "",
) -> object:
    """Reduce *series* (values from parallel members) to one value via *rule*.

    Args:
        series: Values of one attribute across the members being merged.
        rule:   Aggregation rule string.
        region: Region name, used when *rule* is ``"region"``.

    Returns:
        Reduced scalar, or ``None`` when rule is ``"ignore"``.
    """
    if rule in ("ignore", "default"):
        # "ignore"  — don't set the attribute; PyPSA uses its own default.
        # "default" — explicit alias with the same semantics but clearer intent.
        return None
    if rule in ("inf", "+inf"):
        return float("inf")
    if rule in ("-inf", "neginf", "neg_inf"):
        return float("-inf")
    if rule == "region":
        return region
    if rule in ("carrier", "bus"):
        first = series.dropna()
        return str(first.iloc[0]) if not first.empty else None

    numeric = pd.to_numeric(series, errors="coerce")

    if rule == "sum":
        return numeric.sum()
    if rule in ("mean", "weighted_avg"):
        return numeric.mean()
    if rule in ("min", "oldest"):
        return numeric.min()
    if rule in ("max", "newest"):
        return numeric.max()

    # Literal value: return the rule string itself.
    return rule


def _find_province_column(df: pd.DataFrame) -> str | None:
    """Return whichever province column is present (case-insensitive)."""
    for col in df.columns:
        if str(col).strip().lower() == "province":
            return col
    return None


def _build_province_to_region(
    mapping_df: pd.DataFrame | None,
    region_column: str,
) -> tuple[dict[str, str], str]:
    """Return ``(province_name → region_name, effective_region_column)``.

    Looks at the user-requested ``region_column``:

    * ``"province"`` — map every province to its short code.  Falls back to
      the official name when no short code exists.
    * any other value — that column must exist in ``mapping_df``; the value
      in that column becomes the region.

    Args:
        mapping_df:    Parsed ``province_mapping`` sheet, or ``None``.
        region_column: ``settings.region_column``.

    Returns:
        ``(prov → region, region_column)``.  When no mapping is available
        and ``region_column == "province"`` we return ``({}, "province")``
        and the caller falls back to the bus's province as-is.
    """
    region_column = region_column.strip().lower()

    if mapping_df is None or mapping_df.empty:
        return {}, region_column

    # Normalise column names so the lookup is case-insensitive.
    df = mapping_df.copy()
    df.columns = df.columns.str.strip().str.lower()

    # Decide which column to read the region from.
    if region_column == "province":
        target_col = "short"
    elif region_column in df.columns:
        target_col = region_column
    else:
        # Requested column not present — log and fall back to short.
        print(
            f"  Region: column '{region_column}' not in province_mapping "
            f"({sorted(c for c in df.columns if c not in _RESERVED_MAPPING_COLS)}); "
            f"falling back to 'province' / short codes"
        )
        target_col = "short"

    mapping: dict[str, str] = {}
    for _, row in df.iterrows():
        official = row.get("official")
        short = row.get("short")
        target = row.get(target_col)
        if pd.isna(official):
            continue
        region = target if pd.notna(target) else short if pd.notna(short) else official
        if pd.isna(region):
            continue
        mapping[str(official).strip()] = str(region).strip()
        # Also map the short code to itself so that buses already using the
        # short province name still resolve.
        if pd.notna(short):
            mapping[str(short).strip()] = str(region).strip()
    return mapping, region_column


def _build_bus_to_region(
    network: pypsa.Network,
    prov_to_region: dict[str, str],
) -> dict[str, str]:
    """Return ``bus_name → region`` using the bus's province column.

    Buses with a missing or unmappable province map to themselves (so they
    survive as their own one-bus "region").
    """
    prov_col = _find_province_column(network.buses)
    bus_to_region: dict[str, str] = {}
    if prov_col is None:
        # No province column — every bus is its own region (no-op).
        for b in network.buses.index:
            bus_to_region[b] = b
        return bus_to_region

    for b in network.buses.index:
        prov = network.buses.at[b, prov_col]
        if pd.notna(prov):
            prov_str = str(prov).strip()
            region = prov_to_region.get(prov_str, prov_str)
        else:
            region = b  # leave alone
        bus_to_region[b] = region
    return bus_to_region


def _province_column(df: pd.DataFrame) -> str | None:
    """Return whichever ``province`` / ``Province`` column is present, else None."""
    for c in df.columns:
        if str(c).strip().lower() == "province":
            return c
    return None


def _remap_bus_refs(
    network: pypsa.Network,
    bus_to_region: dict[str, str],
    prov_to_region: dict[str, str],
) -> None:
    """Rewrite every component's bus / bus0 / bus1 column to its region.

    Resolution priority for each cell:

    1. ``bus_to_region[current_bus]`` — the normal path: the current bus is
       in ``network.buses`` and we know which region it sits in.
    2. **Province fallback** (single-bus components only): if step 1 misses
       — i.e. the bus is orphan / not in the bus table — and the row carries
       a ``province`` column, look that province up in ``prov_to_region``.
       This is how a generator that was imported with no valid bus but
       *does* carry a province attribute (e.g. a planned unit with no
       network node assigned yet) ends up on the right regional bus
       instead of being silently dropped at ``drop_components_with_missing_buses``.
    3. Keep the original value — the component will be dropped downstream.

    Two-bus components (``lines`` / ``transformers`` / ``links``) only get
    step 1; an orphan endpoint there is a topology error, not a recoverable
    bookkeeping mismatch.
    """
    def _remap(df: pd.DataFrame, cols: list[str], use_prov_fallback: bool = False) -> None:
        if df.empty:
            return
        prov_col = _province_column(df) if use_prov_fallback else None

        for c in cols:
            if c not in df.columns:
                continue

            # Step 1: normal bus → region lookup.
            new_vals = df[c].astype(str).map(bus_to_region)

            # Step 2: province fallback for rows where step 1 missed.
            if prov_col is not None:
                misses_idx = df.index[new_vals.isna()]
                rescued = 0
                for idx in misses_idx:
                    prov = df.at[idx, prov_col]
                    if pd.notna(prov):
                        region = prov_to_region.get(str(prov).strip())
                        if region is not None:
                            new_vals.at[idx] = region
                            rescued += 1
                if rescued:
                    print(
                        f"  Region aggregation: re-homed {rescued} {df.attrs.get('component_name', 'component')} "
                        f"rows from orphan bus to their province's region (column={prov_col!r})"
                    )

            # Step 3: keep the original value where neither step matched.
            df[c] = new_vals.fillna(df[c].astype(str))

    # Tag DataFrames briefly so the print line above can name the component.
    for name in ("generators", "loads", "storage_units", "stores"):
        getattr(network, name).attrs["component_name"] = name

    _remap(network.generators,    ["bus"], use_prov_fallback=True)
    _remap(network.loads,         ["bus"], use_prov_fallback=True)
    _remap(network.storage_units, ["bus"], use_prov_fallback=True)
    _remap(network.stores,        ["bus"], use_prov_fallback=True)
    _remap(network.lines,         ["bus0", "bus1"])
    _remap(network.transformers,  ["bus0", "bus1"])
    _remap(network.links,         ["bus0", "bus1"])


def _compute_region_bus_attrs(
    network: pypsa.Network,
    bus_to_region: dict[str, str],
    rules_df: pd.DataFrame | None = None,
) -> dict[str, dict[str, object]]:
    """Compute member-aggregated attributes for each region's representative bus.

    Aggregation rules are read from *rules_df* (``aggregation_by_region`` sheet,
    component = ``buses``).  When *rules_df* is ``None`` the built-in defaults
    apply: ``x`` / ``y`` → mean, ``v_nom`` → max, everything else → ignore.

    Returns:
        ``{region_name: {attr: value, ...}}``.
    """
    attr_rules, default_rule = _region_rule_lookup(rules_df, "buses")
    buses_df = network.buses

    members_by_region: dict[str, list[str]] = {}
    for old_name, region in bus_to_region.items():
        members_by_region.setdefault(region, []).append(old_name)

    out: dict[str, dict[str, object]] = {}
    for region, members in members_by_region.items():
        sub = buses_df.loc[members]
        attrs: dict[str, object] = {}
        for col in buses_df.columns:
            rule = attr_rules.get(col.lower(), default_rule)
            value = _apply_region_rule(sub[col], rule, region=region)
            if value is None:
                continue
            # Ensure coordinates and v_nom are float; fall back to 0.0 if NaN.
            if col in ("x", "y", "v_nom"):
                try:
                    fval = float(value)  # type: ignore[arg-type]
                    value = fval if pd.notna(fval) else 0.0
                except (TypeError, ValueError):
                    value = 0.0
            attrs[col] = value
        out[region] = attrs
    return out


def _merge_loads_per_bus(network: pypsa.Network) -> int:
    """Sum loads sharing a bus into one merged load named ``load_<bus>``.

    After region aggregation each region typically inherits many individual
    loads (one per pre-aggregation bus).  Functionally the LP is unchanged
    — PyPSA already sums them in the nodal balance — but the model has
    e.g. 193 loads on 16 buses, which is confusing.  This helper collapses
    them: per bus we sum the ``p_set`` time-series across member loads, and
    write a *mean-of-time-series* into the static ``p_set`` so the data
    frame inspection (``network.loads[['bus','p_set']]``) reflects the real
    demand instead of a misleading 0.  PyPSA still uses the time-series
    during optimisation when one is present.

    Returns the number of merged loads in the network afterwards.
    """
    if network.loads.empty:
        return 0

    loads_by_bus = network.loads.groupby("bus").groups
    new_static: dict[str, dict[str, object]] = {}        # name → static attrs
    new_ts: dict[str, pd.Series] = {}                    # name → summed p_set
    to_remove: list[str] = []

    ts_df = getattr(network.loads_t, "p_set", None)
    has_ts = ts_df is not None and not ts_df.empty

    for bus, members in loads_by_bus.items():
        members = list(members)
        new_name = f"load_{bus}"

        # Time-series p_set: sum across all member columns present in p_set.
        merged_series: pd.Series | None = None
        if has_ts:
            cols = [m for m in members if m in ts_df.columns]
            if cols:
                merged_series = ts_df[cols].sum(axis=1)
                new_ts[new_name] = merged_series

        # Static p_set: mean of the merged time-series when we have one
        # (informative for `print(network.loads)`), otherwise the sum of
        # the member static p_sets.
        if merged_series is not None:
            p_set_static = float(merged_series.mean())
        elif "p_set" in network.loads.columns:
            p_set_static = float(pd.to_numeric(
                network.loads.loc[members, "p_set"], errors="coerce"
            ).fillna(0.0).sum())
        else:
            p_set_static = 0.0

        new_static[new_name] = {
            "bus": str(bus),
            "p_set": p_set_static,
        }

        to_remove.extend(members)

    network.remove("Load", to_remove)
    for name, attrs in new_static.items():
        network.add("Load", name, **attrs)
    for name, series in new_ts.items():
        network.loads_t.p_set[name] = series

    return len(new_static)


def _deduplicate_links(
    network: pypsa.Network,
    rules_df: pd.DataFrame | None = None,
) -> int:
    """Collapse parallel Links between the same unordered bus pair.

    Drops self-loops.  For each unique ``{bus0, bus1}`` pair the attribute
    values of parallel links are reduced according to *rules_df*
    (``aggregation_by_region`` sheet, component = ``links``).  When *rules_df*
    is ``None`` the built-in defaults apply: ``p_nom`` → sum,
    ``efficiency`` → min, everything else → ignore.

    ``bus0``, ``bus1``, and ``p_min_pu`` are always written (structural
    columns — rules cannot drop them).  ``p_min_pu`` defaults to ``-1.0``
    for bidirectional links when not covered by a rule.

    Returns the number of unique links remaining.
    """
    if network.links.empty:
        return 0

    attr_rules, default_rule = _region_rule_lookup(rules_df, "links")
    _STRUCTURAL = {"bus0", "bus1", "name"}
    attr_cols = [c for c in network.links.columns if c not in _STRUCTURAL]

    # Collect sub-DataFrames keyed by pair BEFORE removing anything.
    pair_subs: dict[frozenset[str], pd.DataFrame] = {}
    for _, row in network.links.iterrows():
        a, b = str(row["bus0"]), str(row["bus1"])
        if a == b:
            continue
        pair = frozenset((a, b))
        pair_subs[pair] = pd.concat(
            [pair_subs[pair], row.to_frame().T] if pair in pair_subs
            else [row.to_frame().T]
        )

    network.remove("Link", network.links.index)

    for pair, sub in pair_subs.items():
        a, b = sorted(pair)
        merged: dict[str, object] = {"bus0": a, "bus1": b}
        for col in attr_cols:
            rule = attr_rules.get(col.lower(), default_rule)
            value = _apply_region_rule(sub[col], rule, region=a)
            if value is not None:
                merged[col] = value
        if "p_min_pu" not in merged:
            merged["p_min_pu"] = -1.0
        network.add("Link", f"link_{a}_{b}", **merged)

    return len(pair_subs)


def aggregate_by_region(network: pypsa.Network, dashboard: "Dashboard") -> None:
    """Collapse buses into regions; dispatch internally on ``aggregate_by_region``.

    Pipeline contract:

    * Skips silently when ``settings.aggregate_by_region`` is ``False``.
    * Expects transmission to be expressed as ``Link`` components.  If the
      caller chose ``grid_mode = as-is`` (so lines and transformers are still
      KVL-based), this function transparently calls
      :func:`~lib.topology.line_to_link` first using ``settings.link_loss``
      so capacity isn't silently lost during the bus collapse.
    * Modifies *network* in place.

    Args:
        network:   PyPSA Network to modify in place.
        dashboard: Parsed :class:`~lib.settings.Dashboard`.  Reads
            ``settings.aggregate_by_region``, ``settings.region_column``,
            ``settings.link_loss``, and ``dashboard.province_mapping``.
    """
    s = dashboard.settings
    if not s.aggregate_by_region:
        return

    # If the topology step left lines / transformers in place (grid_mode = as-is),
    # convert them to bidirectional Links FIRST so their capacity survives the
    # region collapse instead of being silently dropped at step 5.
    if not network.lines.empty or not network.transformers.empty:
        from lib.topology import line_to_link
        print(
            f"  Region aggregation: grid still has "
            f"{len(network.lines)} lines + {len(network.transformers)} transformers; "
            f"auto-converting to Links (η = 1 − {s.link_loss}) before aggregating"
        )
        line_to_link(network, s.link_loss)

    n_buses_before = len(network.buses)
    n_links_before = len(network.links)

    prov_to_region, effective_col = _build_province_to_region(
        dashboard.province_mapping, s.region_column,
    )
    bus_to_region = _build_bus_to_region(network, prov_to_region)

    rules_df = dashboard.region_rules

    # 1. Compute new bus attributes from each region's member buses BEFORE
    #    mutating anything — coordinates and voltages are aggregated here.
    new_bus_attrs = _compute_region_bus_attrs(network, bus_to_region, rules_df)

    # 2. Rewrite every component's bus reference to its region name.  Old bus
    #    rows still exist for the moment, so PyPSA won't complain.  Single-bus
    #    components fall back to their own `province` column when the current
    #    bus isn't in the bus table (orphan), so they don't get silently
    #    dropped at the end of the pipeline.
    _remap_bus_refs(network, bus_to_region, prov_to_region)

    # 3. Replace the bus table: drop the originals, add one bus per region.
    network.remove("Bus", network.buses.index)
    for region in sorted(new_bus_attrs):
        attrs = new_bus_attrs[region]
        network.add("Bus", region, carrier="AC", **attrs)

    # 4. Collapse parallel links and drop intra-region self-loops.
    n_links_after = _deduplicate_links(network, rules_df)

    # 5. Sum each region's loads into one merged load per bus (preserves the
    #    nodal balance while flattening many loads onto a small region map).
    n_loads_before = len(network.loads)
    n_loads_after = _merge_loads_per_bus(network)

    print(
        f"  Region aggregation: {n_buses_before} buses → "
        f"{len(network.buses)} regions (by '{effective_col}'); "
        f"{n_links_before} links → {n_links_after} unique links; "
        f"{n_loads_before} loads → {n_loads_after} (one per bus)"
    )
