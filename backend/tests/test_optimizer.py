"""
Unit tests for Stages 5 & 6: Critical Load Prioritization & OR-Tools CP-SAT Optimizer.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from restoration.adapter import MockGridAdapter
from restoration.path_generator import TopologyPathGenerator
from restoration.optimizer import RestorationOptimizer
from restoration.models import RestorationStatus


def test_ortools_benchmark_t7_failure_optimization():
    adapter = MockGridAdapter("benchmark")
    components, connections, loads = adapter.load_grid_state()
    path_gen = TopologyPathGenerator(components, connections, loads)

    failed_components = ["T7"]
    affected, _ = path_gen.identify_affected_loads(failed_components)
    routes_by_load = path_gen.generate_all_alternate_routes(affected, failed_components)

    optimizer = RestorationOptimizer(components, affected, routes_by_load)
    result = optimizer.solve(profile="CRITICAL_FIRST")

    assert result["status"] in (RestorationStatus.OPTIMAL, RestorationStatus.FEASIBLE)
    # Hospital H1 and Emergency Shelter E1 MUST be restored
    assert "H1" in result["restored_load_ids"], "Hospital H1 must be prioritized and restored"
    assert "E1" in result["restored_load_ids"], "Emergency Shelter E1 must be prioritized and restored"

    # Capacity limits must be valid
    assert result["is_capacity_valid"] is True
    assert len(result["violations"]) == 0


def test_hospital_prioritization_over_residential():
    """
    Test that when capacity only permits ONE large load or two small loads,
    the high-priority critical Hospital is selected over lower-priority residential loads.
    """
    adapter = MockGridAdapter("benchmark")
    components, connections, loads = adapter.load_grid_state()

    # Artificially constrain F5 to 1.10 MW (base 0.55 -> headroom 0.55 MW)
    # Hospital H1 requires 0.50 MW. Residential loads L2+L3 require 0.35+0.40=0.75 MW.
    for c in components:
        if c.id == "F5":
            c.capacity_mw = 1.10
        elif c.id == "F6":
            c.capacity_mw = 0.70  # F6 has 0 headroom (cannot take any load)

    path_gen = TopologyPathGenerator(components, connections, loads)
    affected, _ = path_gen.identify_affected_loads(["T7"])
    routes_by_load = path_gen.generate_all_alternate_routes(affected, ["T7"])

    optimizer = RestorationOptimizer(components, affected, routes_by_load)
    result = optimizer.solve(profile="CRITICAL_FIRST")

    assert result["status"] == RestorationStatus.OPTIMAL
    # Hospital H1 (0.50 MW) fits in 0.55 MW headroom and MUST be chosen
    assert "H1" in result["restored_load_ids"]
    # L2 and L3 cannot both fit and must be shed/unserved to protect capacity
    assert result["is_capacity_valid"] is True


def test_zero_alternate_paths_handling():
    adapter = MockGridAdapter("no_path")
    components, connections, loads = adapter.load_grid_state()
    path_gen = TopologyPathGenerator(components, connections, loads)

    affected, _ = path_gen.identify_affected_loads(["T7"])
    routes_by_load = path_gen.generate_all_alternate_routes(affected, ["T7"])

    optimizer = RestorationOptimizer(components, affected, routes_by_load)
    result = optimizer.solve()

    assert result["status"] == RestorationStatus.NO_FEASIBLE_RESTORATION
    assert len(result["restored_load_ids"]) == 0
    assert len(result["unserved_load_ids"]) == len(affected)


def test_different_optimization_profiles():
    adapter = MockGridAdapter("benchmark")
    components, connections, loads = adapter.load_grid_state()
    path_gen = TopologyPathGenerator(components, connections, loads)

    affected, _ = path_gen.identify_affected_loads(["T7"])
    routes_by_load = path_gen.generate_all_alternate_routes(affected, ["T7"])

    optimizer = RestorationOptimizer(components, affected, routes_by_load)

    res_crit = optimizer.solve(profile="CRITICAL_FIRST")
    res_demand = optimizer.solve(profile="MAX_DEMAND")
    res_switch = optimizer.solve(profile="MIN_SWITCHING")

    assert res_crit["status"] == RestorationStatus.OPTIMAL
    assert res_demand["status"] == RestorationStatus.OPTIMAL
    assert res_switch["status"] == RestorationStatus.OPTIMAL


if __name__ == "__main__":
    pytest.main(["-v", __file__])
