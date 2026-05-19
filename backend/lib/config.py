"""Load and cache JSON config files from the data/ directory."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

# data/ is one level above the backend/ package (project root)
_DATA_DIR = Path(__file__).resolve().parents[2] / "data"


@lru_cache(maxsize=None)
def load_system_defaults() -> dict:
    path = _DATA_DIR / "system_defaults.json"
    with path.open() as f:
        return json.load(f)


@lru_cache(maxsize=None)
def load_currencies() -> list[dict]:
    path = _DATA_DIR / "currencies.json"
    with path.open() as f:
        return json.load(f)


