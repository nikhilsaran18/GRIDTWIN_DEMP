"""
Unit tests for Stage 8: Before-vs-After Impact Analytics.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pytest
from restoration.models import LoadDemand, LoadType
from restoration.impact_calculator import ImpactCalculator


def test_standard_impact_calculation():
    all_loads = [
        LoadDemand(id="H1", node_id="B_H1", name="Hospital", demand_mw=0.50, is_critical=True),
        LoadDemand(id="E1", node_id="B_E1", name="Emergency", demand_mw=0.25, is_critical=True),
        LoadDemand(id="L2", node_id="B_L2", name="Residential 2", demand_mw=0.35, is_critical=False),
        LoadDemand(id="L3", node_id="B_L3", name="Residential 3", demand_mw=0.40, is_critical=False),
    ]

    affected_loads = all_loads[:]  # All 4 affected (Total demand = 1.50 MW)
    restored_ids = ["H1", "E1", "L2"]  # H1 + E1 + L2 = 1.10 MW restored, L3 = 0.40 MW unserved

    impact = ImpactCalculator.calculate_impact(affected_loads, restored_ids, all_loads)

    assert impact.affected_loads_before == 4
    assert impact.affected_loads_after == 1
    assert impact.restored_loads_count == 3
    assert impact.critical_loads_affected_before == 2
    assert impact.critical_loads_restored_count == 2
    assert impact.critical_loads_affected_after == 0

    assert impact.interrupted_demand_before_mw == 1.50
    assert impact.restored_demand_mw == 1.10
    assert impact.interrupted_demand_after_mw == 0.40

    # Disruption reduction = (1.10 / 1.50) * 100 = 73.33%
    assert impact.disruption_reduction_pct == 73.33
    assert impact.critical_demand_restored_pct == 100.0


def test_zero_interrupted_demand_edge_case():
    all_loads = [
        LoadDemand(id="L1", node_id="B_L1", name="Residential", demand_mw=0.0, is_critical=False)
    ]
    affected_loads = []
    restored_ids = []

    impact = ImpactCalculator.calculate_impact(affected_loads, restored_ids, all_loads)

    assert impact.interrupted_demand_before_mw == 0.0
    assert impact.disruption_reduction_pct == 0.0
    assert impact.critical_demand_restored_pct == 100.0


if __name__ == "__main__":
    pytest.main(["-v", __file__])
