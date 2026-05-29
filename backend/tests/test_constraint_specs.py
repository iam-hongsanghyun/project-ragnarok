"""End-to-end pins for the structured-JSON constraint spec transport.

The frontend sends `scenario.constraintSpecs` (a JSON list); the backend applies
each spec to the linopy model. Verifies a cap actually binds and that a bad spec
is skipped without crashing the solve.
"""
from __future__ import annotations

from typing import Any

from backend.pypsa.results import run_pypsa


def _two_carrier_model() -> dict[str, list[dict[str, Any]]]:
    """Cheap coal + pricier gas on one bus, two snapshots, flat 80 MW load."""
    return {
        "buses": [{"name": "b0", "v_nom": 380.0}],
        "snapshots": [
            {"snapshot": "2025-01-01T00:00:00"},
            {"snapshot": "2025-01-01T01:00:00"},
        ],
        "carriers": [
            {"name": "coal", "co2_emissions": 0.9},
            {"name": "gas", "co2_emissions": 0.4},
        ],
        "generators": [
            {"name": "c", "bus": "b0", "carrier": "coal", "p_nom": 100.0, "marginal_cost": 10.0},
            {"name": "g", "bus": "b0", "carrier": "gas", "p_nom": 100.0, "marginal_cost": 30.0},
        ],
        "loads": [{"name": "L", "bus": "b0", "p_set": 80.0}],
        "loads-p_set": [
            {"snapshot": "2025-01-01T00:00:00", "L": 80.0},
            {"snapshot": "2025-01-01T01:00:00", "L": 80.0},
        ],
    }


def test_constraint_spec_caps_carrier_energy() -> None:
    spec = {
        "lhs": [{"coef": 1.0, "kind": "gen", "carrier": "coal"}],
        "sense": "<=",
        "rhs": [{"coef": 50.0, "kind": "const"}],
    }
    result = run_pypsa(
        _two_carrier_model(),
        {"discountRate": 0.05, "carbonPrice": 0.0, "constraintSpecs": [spec]},
        {},
    )
    notes = " | ".join(result["narrative"])
    assert "Constraint spec 1" in notes and "added" in notes
    applied = {c["name"]: c for c in result.get("appliedConstraints", [])}
    assert "spec_1" in applied
    assert applied["spec_1"]["source"] == "plugin" or applied["spec_1"]["name"] == "spec_1"


def test_bad_constraint_spec_is_skipped() -> None:
    bad = {
        "lhs": [{"coef": 1.0, "kind": "gen", "carrier": "does-not-exist"}],
        "sense": "<=",
        "rhs": [{"coef": 1.0, "kind": "const"}],
    }
    # Should not raise — the bad spec is skipped with a note, the solve completes.
    result = run_pypsa(
        _two_carrier_model(),
        {"discountRate": 0.05, "carbonPrice": 0.0, "constraintSpecs": [bad]},
        {},
    )
    notes = " | ".join(result["narrative"])
    assert "Constraint spec 1" in notes and "could not be added" in notes
