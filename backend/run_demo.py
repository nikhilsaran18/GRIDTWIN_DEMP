"""
Visual Demonstration Script for GridTwin Restoration & Optimization Engine.

Run this script to simulate an outage on Transformer T7 and generate the full
restoration report, capacity validation, strategy ranking, and recovery sequence.
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from restoration.service import RestorationService
from restoration.adapter import MockGridAdapter
from restoration.models import ActionType


def run_visual_demo():
    print("=" * 60)
    print("  GRIDTWIN — AI-ASSISTED RESTORATION OPTIMIZER (MEMBER 2)")
    print("  Track: Critical Grid & Power Shield | Status: SIMULATED")
    print("=" * 60)

    # Initialize service with benchmark grid adapter
    adapter = MockGridAdapter("benchmark")
    service = RestorationService(adapter=adapter)

    failed_component = "T7"
    print(f"\n[!] INITIATING CASCADE RESTORATION PIPELINE FOR FAILED COMPONENT: {failed_component}")
    print("-" * 60)

    # Run optimizer
    result = service.optimize_restoration(failed_components=[failed_component])

    print(f"FAILED COMPONENT:       {', '.join(result.failed_components)}")
    print(f"AFFECTED LOADS (LOST):  {', '.join(result.affected_load_ids)}")
    print(f"CANDIDATE STRATEGIES:   {1 + len(result.alternative_strategies)}")
    print(f"OPTIMIZATION STATUS:    {result.status.value}")

    rec = result.recommended_strategy
    if not rec:
        print("\n[X] NO FEASIBLE RESTORATION FOUND")
        print(f"Reason: {result.explanation}")
        return

    print("\n" + "=" * 60)
    print(f"  RECOMMENDED STRATEGY: {rec.strategy_id} (Rank #{rec.rank})")
    print(f"  {rec.name}")
    print("=" * 60)

    print("\n[1] RECOVERY ACTION SEQUENCE:")
    for action in rec.recovery_sequence:
        action_type_str = action.action.value
        if action.action == ActionType.ISOLATE:
            badge = "[ISOLATE] "
        elif action.action == ActionType.REROUTE:
            badge = "[REROUTE] "
        else:
            badge = "[RESTORE] "
        print(f"  Step {action.step:02d}: {badge:<10} {action.details}")

    print("\n[2] CAPACITY & THERMAL LOADING VALIDATION:")
    print("  " + "-" * 66)
    print(f"  {'Component':<10} {'Base':<8} {'Added':<8} {'Post-Rest.':<10} {'Cap.':<8} {'Util %':<8} {'Status':<18}")
    print("  " + "-" * 66)

    for fu in result.capacity_summary.get("feeders", []):
        print(
            f"  {fu.id:<10} {fu.base_load_mw:>5.2f}MW {fu.added_restoration_load_mw:>5.2f}MW "
            f"{fu.post_restoration_load_mw:>6.2f}MW {fu.capacity_mw:>5.2f}MW {fu.utilization_pct:>6.1f}%  {fu.status:<18}"
        )
    for tu in result.capacity_summary.get("transformers", []):
        print(
            f"  {tu.id:<10} {tu.base_load_mw:>5.2f}MW {tu.added_restoration_load_mw:>5.2f}MW "
            f"{tu.post_restoration_load_mw:>6.2f}MW {tu.capacity_mw:>5.2f}MW {tu.utilization_pct:>6.1f}%  {tu.status:<18}"
        )
    print("  " + "-" * 66)

    print("\n[3] CRITICAL LOAD PRESERVATION:")
    crit = rec.critical_loads_summary
    print(f"  Total Critical Facilities Affected: {crit.total_critical}")
    print(f"  Critical Facilities Restored:       {crit.restored_critical} / {crit.total_critical} ({crit.restored_percentage:.1f}%)")
    for detail in crit.critical_loads_details:
        status_tag = "RESTORED" if detail["restored"] else "UNSERVED"
        print(f"    - {detail['name']} ({detail['id']}): {status_tag} ({detail['demand_mw']:.2f} MW)")

    print("\n[4] OUTAGE DISRUPTION IMPACT:")
    imp = rec.impact
    print(f"  Pre-Mitigation Disrupted Demand:  {imp.interrupted_demand_before_mw:.2f} MW")
    print(f"  Post-Restoration Restored Demand: {imp.restored_demand_mw:.2f} MW")
    print(f"  Remaining Unserved Demand:        {imp.interrupted_demand_after_mw:.2f} MW")
    print(f"  Disruption Reduction:             {imp.disruption_reduction_pct:.1f}%")

    if result.alternative_strategies:
        print("\n[5] ALTERNATIVE STRATEGY COMPARISON:")
        for alt in result.alternative_strategies:
            print(f"  Rank #{alt.rank} - {alt.name}:")
            print(f"    Critical Restored: {alt.critical_loads_summary.restored_percentage:.1f}% | Restored MW: {alt.impact.restored_demand_mw:.2f} MW | Max Feeder Util: {alt.max_feeder_utilization_pct:.1f}%")

    print("\n" + "=" * 60)
    print("  RESTORATION OPTIMIZATION COMPLETE (STATUS: OPTIMAL)")
    print("=" * 60)


if __name__ == "__main__":
    run_visual_demo()
