"""
Restoration Service Orchestration Layer for GridTwin.

Responsibilities:
- Encapsulate end-to-end restoration workflow without exposing internal logic to API routes.
- Handle adapter ingestion, path generation, OR-Tools optimization, strategy ranking, and impact analysis.
- Provide clean, robust exception handling and structured Pydantic results.
"""

from typing import List, Dict, Any, Optional
from restoration.models import (
    RestorationResult,
    RestorationStatus,
    ComponentUtilization,
    StrategyResult,
)
from restoration.adapter import BaseGridAdapter, MockGridAdapter
from restoration.path_generator import TopologyPathGenerator
from restoration.capacity_checker import CapacityChecker
from restoration.strategy_ranker import StrategyRanker
from restoration.impact_calculator import ImpactCalculator


class RestorationService:
    """
    Core service coordinating the GridTwin restoration pipeline.
    """

    def __init__(self, adapter: Optional[BaseGridAdapter] = None):
        self.adapter = adapter or MockGridAdapter("benchmark")

    def optimize_restoration(
        self,
        failed_components: Optional[List[str]] = None,
        custom_adapter: Optional[BaseGridAdapter] = None,
    ) -> RestorationResult:
        """
        Executes the complete restoration optimization pipeline:
        1. Ingest grid state and failure set via adapter
        2. Identify affected loads losing power
        3. Discover alternate candidate supply paths
        4. Validate feeder & transformer capacity limits
        5. Formulate & solve OR-Tools CP-SAT combinatorial optimization
        6. Generate, score, and rank multiple restoration strategies
        7. Calculate baseline vs. post-restoration impact reduction
        8. Synthesize dynamic recovery action sequence
        """
        active_adapter = custom_adapter or self.adapter
        components, connections, loads = active_adapter.load_grid_state()

        if failed_components is None:
            failed_components = ["T7"]  # Default benchmark failure

        # 1. Topology & Connectivity Analysis
        path_gen = TopologyPathGenerator(components, connections, loads)
        affected_loads, still_served_loads = path_gen.identify_affected_loads(failed_components)
        routes_by_load = path_gen.generate_all_alternate_routes(affected_loads, failed_components)

        capacity_checker = CapacityChecker(components)

        # 2. Handle Case: No affected loads
        if not affected_loads:
            return RestorationResult(
                status=RestorationStatus.OPTIMAL,
                simulation_mode="SIMULATED",
                failed_components=failed_components,
                affected_load_ids=[],
                recommended_strategy=None,
                alternative_strategies=[],
                recovery_sequence=[],
                capacity_summary=capacity_checker.evaluate_route_set_capacity([], {}, failed_components=failed_components)[1],
                impact=ImpactCalculator.calculate_impact([], [], loads),
                explanation="No loads were interrupted by the specified failure state.",
            )

        # 3. Multi-Strategy Generation & Ranking
        ranker = StrategyRanker(
            components=components,
            all_loads=loads,
            affected_loads=affected_loads,
            failed_components=failed_components,
            routes_by_load=routes_by_load,
            capacity_checker=capacity_checker,
        )

        ranked_strategies = ranker.generate_and_rank_strategies()

        # 4. Handle Case: No feasible restoration found or 0 loads could be safely restored
        has_feasible_strat = ranked_strategies and any(
            s.is_feasible and len(s.restored_load_ids) > 0 for s in ranked_strategies
        )

        if not has_feasible_strat:
            has_routes = any(len(r) > 0 for r in routes_by_load.values())
            if not has_routes:
                reason = "No alternate topological supply paths exist connecting operational substations to affected loads"
            else:
                # Find which components have insufficient headroom
                bottlenecks = []
                for f in capacity_checker.feeders.values():
                    headroom = f.capacity_mw - f.base_load_mw
                    bottlenecks.append(f"Feeder {f.id} (Capacity: {f.capacity_mw:.2f}MW, Base: {f.base_load_mw:.2f}MW, Headroom: {headroom:.2f}MW)")
                for t in capacity_checker.transformers.values():
                    headroom = t.capacity_mw - t.base_load_mw
                    bottlenecks.append(f"Transformer {t.id} (Capacity: {t.capacity_mw:.2f}MW, Base: {t.base_load_mw:.2f}MW, Headroom: {headroom:.2f}MW)")
                reason = f"Insufficient capacity on alternate paths to safely restore any affected load. Bottlenecks: {'; '.join(bottlenecks)}"

            empty_impact = ImpactCalculator.calculate_impact(
                affected_loads=affected_loads,
                restored_load_ids=[],
                all_loads=loads,
            )

            # Check unserved critical loads
            unserved_crit = [l.name for l in affected_loads if l.is_critical]
            crit_msg = f" Critical facilities remaining unserved: {', '.join(unserved_crit)}." if unserved_crit else ""

            return RestorationResult(
                status=RestorationStatus.NO_FEASIBLE_RESTORATION,
                simulation_mode="SIMULATED",
                failed_components=failed_components,
                affected_load_ids=[l.id for l in affected_loads],
                recommended_strategy=None,
                alternative_strategies=ranked_strategies,
                recovery_sequence=[],
                capacity_summary=capacity_checker.evaluate_route_set_capacity([], {}, failed_components=failed_components)[1],
                impact=empty_impact,
                diagnostics={"reason": reason},
                explanation=f"NO_FEASIBLE_RESTORATION: {reason}.{crit_msg}",
            )

        # 5. Extract Recommended Strategy (Rank 1)
        recommended = ranked_strategies[0]
        alternatives = ranked_strategies[1:]

        # Get utilization for recommended strategy
        rec_routes_list = [
            r
            for lid, r in path_gen.generate_all_alternate_routes(affected_loads, failed_components).items()
            if lid in recommended.selected_routes
            for r in r
            if r.route_id == recommended.selected_routes[lid]
        ]
        load_demands = {l.id: l.demand_mw for l in affected_loads}
        _, cap_summary, _ = capacity_checker.evaluate_route_set_capacity(
            rec_routes_list, load_demands, failed_components=failed_components
        )

        # Hospital status reporting
        hospitals_unserved = [
            l.name for l in affected_loads if l.is_critical and l.id in recommended.unserved_load_ids
        ]
        hosp_note = (
            f"\n[WARNING] Critical loads unserved: {', '.join(hospitals_unserved)} due to capacity limits."
            if hospitals_unserved
            else ""
        )

        explanation = (
            f"Recommended Strategy '{recommended.name}' (Rank 1):\n"
            f"- Restored {recommended.critical_loads_summary.restored_percentage:.1f}% critical loads "
            f"({recommended.critical_loads_summary.restored_critical}/{recommended.critical_loads_summary.total_critical})\n"
            f"- Outage disruption reduced by {recommended.impact.disruption_reduction_pct:.1f}% "
            f"({recommended.impact.restored_demand_mw:.2f} MW / {recommended.impact.interrupted_demand_before_mw:.2f} MW)\n"
            f"- Maximum feeder loading kept at {recommended.max_feeder_utilization_pct:.1f}% (Within safe rated thermal limits)\n"
            f"- Maximum transformer loading kept at {recommended.max_transformer_utilization_pct:.1f}%\n"
            f"- Total recovery sequence: {len(recommended.recovery_sequence)} verified actions{hosp_note}"
        )

        return RestorationResult(
            status=RestorationStatus.OPTIMAL,
            simulation_mode="SIMULATED",
            failed_components=failed_components,
            affected_load_ids=[l.id for l in affected_loads],
            recommended_strategy=recommended,
            alternative_strategies=alternatives,
            recovery_sequence=recommended.recovery_sequence,
            capacity_summary=cap_summary,
            impact=recommended.impact,
            diagnostics={"strategy_count": len(ranked_strategies)},
            explanation=explanation,
        )
