"""
Complete End-to-End Hackathon Demonstration Test for GridTwin Restoration Module.

Tests the full pipeline on the benchmark scenario:
- Failure of Transformer T7
- Hospital H1 and Emergency Shelter E1 critical prioritization
- Rerouting via Feeder F5 / Transformer T8 and Feeder F6 / Transformer T9
- Capacity limit enforcement preventing secondary cascades
- Generation of ranked strategies and recovery sequence
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from restoration.service import RestorationService
from restoration.adapter import MockGridAdapter
from restoration.models import RestorationStatus, ActionType


def test_hackathon_end_to_end_t7_outage_scenario():
    adapter = MockGridAdapter("benchmark")
    service = RestorationService(adapter=adapter)

    result = service.optimize_restoration(failed_components=["T7"])

    # 1. Status must be OPTIMAL
    assert result.status == RestorationStatus.OPTIMAL
    assert result.simulation_mode == "SIMULATED"
    assert result.failed_components == ["T7"]

    # 2. Affected loads must be H1, E1, L2, L3
    assert set(result.affected_load_ids) == {"H1", "E1", "L2", "L3"}

    # 3. Recommended strategy must be Rank 1
    assert result.recommended_strategy is not None
    assert result.recommended_strategy.rank == 1

    # 4. Critical loads (Hospital H1, Emergency E1) must be 100% restored
    crit = result.recommended_strategy.critical_loads_summary
    assert crit.total_critical == 2
    assert crit.restored_critical == 2
    assert crit.unserved_critical == 0
    assert crit.restored_percentage == 100.0
    assert "H1" in result.recommended_strategy.restored_load_ids
    assert "E1" in result.recommended_strategy.restored_load_ids

    # 5. Feeder and Transformer capacity must be strictly respected (No secondary cascade)
    f_utils = result.capacity_summary.get("feeders", [])
    t_utils = result.capacity_summary.get("transformers", [])

    for fu in f_utils:
        if fu.id in result.failed_components:
            assert fu.status == "FAILED / ISOLATED"
        else:
            assert fu.post_restoration_load_mw <= fu.capacity_mw, f"Feeder {fu.id} overloaded!"
            assert fu.status == "FEASIBLE"

    for tu in t_utils:
        if tu.id in result.failed_components:
            assert tu.status == "FAILED / ISOLATED"
        else:
            assert tu.post_restoration_load_mw <= tu.capacity_mw, f"Transformer {tu.id} overloaded!"
            assert tu.status == "FEASIBLE"

    # 6. Impact calculation must show substantial disruption reduction
    impact = result.impact
    assert impact is not None
    assert impact.affected_loads_before == 4
    assert impact.restored_loads_count >= 2
    assert impact.disruption_reduction_pct > 50.0
    assert impact.critical_demand_restored_pct == 100.0

    # 7. Recovery sequence must have correct action structure
    seq = result.recovery_sequence
    assert len(seq) >= 4

    # Step 1 must be ISOLATE T7
    assert seq[0].action == ActionType.ISOLATE
    assert seq[0].target == "T7"

    # Hospital H1 must be restored before any non-critical load
    restore_actions = [a for a in seq if a.action == ActionType.RESTORE]
    assert restore_actions[0].target == "H1", "Hospital H1 must be the first restored load"


def test_hackathon_insufficient_capacity_scenario():
    """
    Tests grid scenario where all alternate paths are bottlenecked.
    Should report clear reason without crashing.
    """
    adapter = MockGridAdapter("bottleneck")
    service = RestorationService(adapter=adapter)

    result = service.optimize_restoration(failed_components=["T7"])

    assert result.status == RestorationStatus.NO_FEASIBLE_RESTORATION
    assert len(result.recovery_sequence) == 0
    assert "reason" in result.diagnostics or len(result.explanation) > 0


if __name__ == "__main__":
    pytest.main(["-v", __file__])
