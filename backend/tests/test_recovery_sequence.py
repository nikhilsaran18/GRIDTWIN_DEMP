"""
Unit tests for Stage 9: Dynamic Recovery Sequence Generation.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from restoration.models import ActionType, CandidateRoute, LoadDemand, LoadType
from restoration.recovery_sequence import RecoverySequenceGenerator


def test_recovery_sequence_generation_order():
    failed_components = ["T7"]
    h1 = LoadDemand(id="H1", node_id="B_H1", name="Hospital H1", demand_mw=0.50, is_critical=True, priority=100)
    e1 = LoadDemand(id="E1", node_id="B_E1", name="Emergency E1", demand_mw=0.25, is_critical=True, priority=90)
    l2 = LoadDemand(id="L2", node_id="B_L2", name="Residential L2", demand_mw=0.35, is_critical=False, priority=30)

    selected_routes = {
        "H1": CandidateRoute(
            route_id="R_H1_F5",
            load_id="H1",
            source_substation_id="S1",
            path_nodes=["S1", "T8", "F5", "B_F5", "B_H1"],
            feeders_used=["F5"],
            transformers_used=["T8"],
        ),
        "E1": CandidateRoute(
            route_id="R_E1_F5",
            load_id="E1",
            source_substation_id="S1",
            path_nodes=["S1", "T8", "F5", "B_F5", "B_E1"],
            feeders_used=["F5"],
            transformers_used=["T8"],
        ),
        "L2": CandidateRoute(
            route_id="R_L2_F6",
            load_id="L2",
            source_substation_id="S2",
            path_nodes=["S2", "T9", "F6", "B_F6", "B_L2"],
            feeders_used=["F6"],
            transformers_used=["T9"],
        ),
    }

    # Pass in unsorted order: [L2, E1, H1]
    sequence = RecoverySequenceGenerator.generate_sequence(
        failed_components=failed_components,
        selected_routes=selected_routes,
        restored_loads=[l2, e1, h1],
    )

    assert len(sequence) >= 5

    # 1. Step 1 must be ISOLATE T7
    assert sequence[0].action == ActionType.ISOLATE
    assert sequence[0].target == "T7"

    # 2. Middle steps must be REROUTE
    reroute_steps = [s for s in sequence if s.action == ActionType.REROUTE]
    assert len(reroute_steps) == 3

    # 3. Final steps must be RESTORE sorted by (critical, priority)
    restore_steps = [s for s in sequence if s.action == ActionType.RESTORE]
    assert len(restore_steps) == 3
    assert restore_steps[0].target == "H1", "Hospital H1 must be restored first"
    assert restore_steps[1].target == "E1", "Emergency E1 must be restored second"
    assert restore_steps[2].target == "L2", "Residential L2 must be restored third"


if __name__ == "__main__":
    pytest.main(["-v", __file__])
