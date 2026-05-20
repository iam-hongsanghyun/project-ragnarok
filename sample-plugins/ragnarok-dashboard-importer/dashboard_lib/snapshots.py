"""Snapshot window slicing for PyPSA networks."""
from __future__ import annotations

from datetime import datetime

import pandas as pd
import pypsa


def slice_snapshots(network: pypsa.Network, start: str, length: int) -> None:
    """Slice network snapshots to ``[start, start + length)``.

    Matches on month / day / hour only, so the year embedded in snapshot
    labels does not have to match the year in *start*.

    Args:
        network: PyPSA Network to modify in place.
        start: Snapshot start timestamp in ``dd/mm/yyyy HH:MM`` format.
        length: Number of snapshots (hours) to retain.

    Raises:
        ValueError: When no snapshot matches the requested month/day/hour.
    """
    dt = datetime.strptime(start, "%d/%m/%Y %H:%M")

    idx = pd.to_datetime(network.snapshots, dayfirst=True)
    matches = (idx.month == dt.month) & (idx.day == dt.day) & (idx.hour == dt.hour)

    if not matches.any():
        raise ValueError(
            f"No snapshot matching month={dt.month} day={dt.day} hour={dt.hour}"
        )

    pos = int(matches.argmax())
    network.snapshots = network.snapshots[pos : pos + length]
    print(f"  Snapshots sliced: {start} + {length}h  (index {pos}–{pos + length - 1})")
