"""
Unit tests for Stage 7: Multi-Strategy Generation and Ranking.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from restoration.adapter import MockGridAdapter
from restoration.path_generator import TopologyPathGenerator
from restoration.strategy_ranker import StrategyRanker


def test_strategy_generation_and_ranking():
    adapter = MockGridAdapter("benchmark")
    components, connections, loads = adapter.load_grid_state()
    path_gen = TopologyPathGenerator(components, connections, loads)

    failed_components = ["T7"]
    affected, _ = path_gen.identify_affected_loads(failed_components)
    routes_by_load = path_gen.generate_all_alternate_routes(affected, failed_components)

    ranker = StrategyRanker(
        components=components,
        all_loads=loads,
        affected_loads=affected,
        failed_components=failed_components,
        routes_by_load=routes_by_load,
    )

    strategies = ranker.generate_and_rank_strategies()

    assert len(strategies) >= 2, "Should generate at least 2 distinct restoration strategies"

    # Verify ranks are ordered 1, 2, ...
    for idx, strat in enumerate(strategies, start=1):
        assert strat.rank == idx

    # Top ranked strategy (Rank 1) must have 100% critical load restoration
    top_strat = strategies[0]
    assert top_strat.critical_loads_summary.restored_percentage == 100.0
    assert "H1" in top_strat.restored_load_ids
    assert top_strat.is_feasible is True
    assert len(top_strat.explanation) > 0


def test_explainable_ranking_criteria():
    adapter = MockGridAdapter("benchmark")
    components, connections, loads = adapter.load_grid_state()
    path_gen = TopologyPathGenerator(components, connections, loads)

    failed_components = ["T7"]
    affected, _ = path_gen.identify_affected_loads(failed_components)
    routes_by_load = path_gen.generate_all_alternate_routes(affected, failed_components)

    ranker = StrategyRanker(
        components=components,
        all_loads=loads,
        affected_loads=affected,
        failed_components=failed_components,
        routes_by_load=routes_by_load,
    )

    strategies = ranker.generate_and_rank_strategies()

    for s in strategies:
        assert s.impact.interrupted_demand_before_mw > 0
        assert s.impact.restored_demand_mw > 0
        assert s.max_feeder_utilization_pct <= 100.0


if __name__ == "__main__":
    pytest.main(["-v", __file__])
