"""Load and cache backend-owned JSON config files."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

# backend/config sits one level above backend/lib/
_CONFIG_DIR = Path(__file__).resolve().parents[1] / "config"


@lru_cache(maxsize=None)
def load_system_defaults() -> dict:
    path = _CONFIG_DIR / "system_defaults.json"
    with path.open() as f:
        return json.load(f)

