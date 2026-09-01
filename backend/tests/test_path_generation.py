"""
Unit tests for Stage 3: NetworkX Topology Analysis and Alternate Path Generation.
"""

import sys
import os

# Add backend directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from restoration.adapter import MockGridAdapter
from restoration.path_generator import TopologyPathGenerator


def test_topology_initialization():
    adapter = MockGridAdapter("benchmark")
    components, connections, loads = adapter.load_grid_state()
    path_gen = TopologyPathGenerator(components, connections, loads)

    assert len(path_gen.components) == 16
    assert len(path_gen.connections) == 18
    assert len(path_gen.loads) == 5
    assert path_gen.master_graph.number_of_nodes() == 16


def test_identify_affected_loads_on_t7_failure():
    adapter = MockGridAdapter("benchmark")
    components, connections, loads = adapter.load_grid_state()
    path_gen = TopologyPathGenerator(components, connections, loads)

    failed_components = ["T7"]
    affected, still_served = path_gen.identify_affected_loads(failed_components)

    affected_ids = {l.id for l in affected}
    still_served_ids = {l.id for l in still_served}

    # H1, E1, L2, L3 are supplied via T7/F3 in baseline
    assert affected_ids == {"H1", "E1", "L2", "L3"}
    # L4 is supplied via T8/F5 and should remain served
    assert still_served_ids == {"L4"}


def test_alternate_routes_discovery():
    adapter = MockGridAdapter("benchmark")
    components, connections, loads = adapter.load_grid_state()
    path_gen = TopologyPathGenerator(components, connections, loads)

    failed_components = ["T7"]
    affected, _ = path_gen.identify_affected_loads(failed_components)

    routes_by_load = path_gen.generate_all_alternate_routes(affected, failed_components)

    # Verify Hospital H1 has candidate alternate paths
    assert "H1" in routes_by_load
    h1_routes = routes_by_load["H1"]
    assert len(h1_routes) >= 2, "Hospital H1 should have at least 2 alternate paths (via F5 and via F6)"

    # Verify that T7 is NOT in any candidate route
    for load_id, routes in routes_by_load.items():
        for r in routes:
            assert "T7" not in r.path_nodes, f"Failed component T7 found in route {r.route_id}"
            assert "T7" not in r.transformers_used

    # Verify that H1 has a route via F5 (T8) and a route via F6 (T9)
    feeders_used_h1 = {f for r in h1_routes for f in r.feeders_used}
    assert "F5" in feeders_used_h1
    assert "F6" in feeders_used_h1


def test_islanded_grid_no_alternate_path():
    adapter = MockGridAdapter("no_path")
    components, connections, loads = adapter.load_grid_state()
    path_gen = TopologyPathGenerator(components, connections, loads)

    failed_components = ["T7"]
    affected, _ = path_gen.identify_affected_loads(failed_components)

    routes_by_load = path_gen.generate_all_alternate_routes(affected, failed_components)

    # In islanded grid with no tie-switches, there should be zero alternate paths
    for load in affected:
        assert len(routes_by_load[load.id]) == 0, f"Expected 0 alternate paths for {load.id}, got {len(routes_by_load[load.id])}"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
