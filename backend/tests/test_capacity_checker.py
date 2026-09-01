"""
Unit tests for Stage 4: Feeder and Transformer Capacity Validation.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from restoration.adapter import MockGridAdapter
from restoration.capacity_checker import CapacityChecker
from restoration.path_generator import TopologyPathGenerator


def test_capacity_checker_initialization():
    adapter = MockGridAdapter("benchmark")
    components, _, _ = adapter.load_grid_state()
    checker = CapacityChecker(components)

    assert len(checker.feeders) == 3
    assert len(checker.transformers) == 3
    assert "F5" in checker.feeders
    assert "T8" in checker.transformers


def test_feasible_route_capacity_evaluation():
    adapter = MockGridAdapter("benchmark")
    components, connections, loads = adapter.load_grid_state()
    checker = CapacityChecker(components)
    path_gen = TopologyPathGenerator(components, connections, loads)

    affected, _ = path_gen.identify_affected_loads(["T7"])
    routes_by_load = path_gen.generate_all_alternate_routes(affected, ["T7"])

    # Select route for Hospital H1 via F5 (T8)
    h1_f5_route = next(r for r in routes_by_load["H1"] if "F5" in r.feeders_used)

    is_feasible, summary, violations = checker.evaluate_route_set_capacity(
        selected_routes=[h1_f5_route],
        load_demands={"H1": 0.50}
    )

    assert is_feasible is True
    assert len(violations) == 0

    # Feeder F5: base 0.55 MW + 0.50 MW = 1.05 MW / 1.50 MW (70.0% utilization)
    f5_util = next(u for u in summary["feeders"] if u.id == "F5")
    assert f5_util.post_restoration_load_mw == 1.05
    assert f5_util.utilization_pct == 70.0
    assert f5_util.margin_mw == 0.45
    assert f5_util.status == "FEASIBLE"


def test_feeder_capacity_overload_rejection():
    adapter = MockGridAdapter("benchmark")
    components, connections, loads = adapter.load_grid_state()
    checker = CapacityChecker(components)
    path_gen = TopologyPathGenerator(components, connections, loads)

    affected, _ = path_gen.identify_affected_loads(["T7"])
    routes_by_load = path_gen.generate_all_alternate_routes(affected, ["T7"])

    # Attempt to route ALL 4 affected loads through F5 (0.50 + 0.25 + 0.35 + 0.40 = 1.50 MW added to 0.55 MW base = 2.05 MW > 1.50 MW)
    f5_routes = []
    for l_id in ["H1", "E1", "L2", "L3"]:
        r_f5 = next((r for r in routes_by_load[l_id] if "F5" in r.feeders_used), None)
        if r_f5:
            f5_routes.append(r_f5)

    is_feasible, summary, violations = checker.evaluate_route_set_capacity(
        selected_routes=f5_routes,
        load_demands={"H1": 0.50, "E1": 0.25, "L2": 0.35, "L3": 0.40}
    )

    assert is_feasible is False
    assert any("F5" in v for v in violations)

    f5_util = next(u for u in summary["feeders"] if u.id == "F5")
    assert f5_util.status == "OVERLOADED"
    assert f5_util.post_restoration_load_mw > f5_util.capacity_mw


def test_transformer_capacity_overload_rejection():
    adapter = MockGridAdapter("bottleneck")
    components, connections, loads = adapter.load_grid_state()
    checker = CapacityChecker(components)
    path_gen = TopologyPathGenerator(components, connections, loads)

    affected, _ = path_gen.identify_affected_loads(["T7"])
    routes_by_load = path_gen.generate_all_alternate_routes(affected, ["T7"])

    h1_route = routes_by_load["H1"][0]
    is_feasible, summary, violations = checker.evaluate_route_set_capacity(
        selected_routes=[h1_route],
        load_demands={"H1": 0.50}
    )

    assert is_feasible is False
    assert len(violations) > 0


if __name__ == "__main__":
    pytest.main(["-v", __file__])
