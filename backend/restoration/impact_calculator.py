"""
Before-vs-After Outage Impact Analytics for GridTwin Restoration.

Calculates:
- Baseline interrupted demand vs. post-restoration served demand.
- Disruption reduction percentage.
- Critical load preservation percentage.
- Safe handling of edge cases (e.g. 0 before demand).
"""

from typing import List, Dict, Set
from restoration.models import LoadDemand, ImpactAnalysis


class ImpactCalculator:
    """
    Computes comparative metrics between the pre-mitigation failure baseline and the post-restoration state.
    """

    @staticmethod
    def calculate_impact(
        affected_loads: List[LoadDemand],
        restored_load_ids: List[str],
        all_loads: List[LoadDemand],
    ) -> ImpactAnalysis:
        """
        Calculates before vs. after impact metrics.
        """
        restored_id_set: Set[str] = set(restored_load_ids)
        affected_id_set: Set[str] = {l.id for l in affected_loads}

        affected_before_count = len(affected_loads)
        restored_count = len([l for l in affected_loads if l.id in restored_id_set])
        affected_after_count = affected_before_count - restored_count

        critical_affected_before = [l for l in affected_loads if l.is_critical]
        critical_affected_before_count = len(critical_affected_before)
        critical_restored = [l for l in critical_affected_before if l.id in restored_id_set]
        critical_restored_count = len(critical_restored)
        critical_affected_after_count = critical_affected_before_count - critical_restored_count

        interrupted_before_mw = sum(l.demand_mw for l in affected_loads)
        restored_mw = sum(l.demand_mw for l in affected_loads if l.id in restored_id_set)
        interrupted_after_mw = max(0.0, interrupted_before_mw - restored_mw)

        # Disruption reduction percentage: ((before - after) / before) * 100
        if interrupted_before_mw > 1e-6:
            disruption_reduction_pct = (restored_mw / interrupted_before_mw) * 100.0
        else:
            disruption_reduction_pct = 0.0

        # Critical demand restored percentage
        critical_before_mw = sum(l.demand_mw for l in critical_affected_before)
        critical_restored_mw = sum(l.demand_mw for l in critical_restored)

        if critical_before_mw > 1e-6:
            critical_demand_restored_pct = (critical_restored_mw / critical_before_mw) * 100.0
        else:
            critical_demand_restored_pct = 100.0 if critical_affected_before_count == 0 else 0.0

        return ImpactAnalysis(
            affected_loads_before=affected_before_count,
            affected_loads_after=affected_after_count,
            restored_loads_count=restored_count,
            critical_loads_affected_before=critical_affected_before_count,
            critical_loads_affected_after=critical_affected_after_count,
            critical_loads_restored_count=critical_restored_count,
            interrupted_demand_before_mw=round(interrupted_before_mw, 3),
            interrupted_demand_after_mw=round(interrupted_after_mw, 3),
            restored_demand_mw=round(restored_mw, 3),
            disruption_reduction_pct=round(disruption_reduction_pct, 2),
            critical_demand_restored_pct=round(critical_demand_restored_pct, 2),
        )
