"""
Multi-Strategy Generation and Explainable Ranking for GridTwin Restoration.

Responsibilities:
- Explore multiple distinct, mathematically verified restoration strategies.
- Compute comprehensive impact, capacity utilization, and recovery sequences for each strategy.
- Rank feasible strategies using transparent, multi-criteria decision logic.
- Produce explainable rationale for why the recommended strategy won.
"""

from typing import List, Dict, Tuple, Optional, Set
from restoration.models import (
    GridComponent,
    LoadDemand,
    CandidateRoute,
    StrategyResult,
    CriticalLoadsSummary,
    ImpactAnalysis,
    RestorationAction,
    ComponentType,
    RestorationStatus,
)
from restoration.capacity_checker import CapacityChecker
from restoration.impact_calculator import ImpactCalculator
from restoration.recovery_sequence import RecoverySequenceGenerator
from restoration.optimizer import RestorationOptimizer


class StrategyRanker:
    """
    Generates, evaluates, and ranks multiple restoration strategies.
    """

    def __init__(
        self,
        components: List[GridComponent],
        all_loads: List[LoadDemand],
        affected_loads: List[LoadDemand],
        failed_components: List[str],
        routes_by_load: Dict[str, List[CandidateRoute]],
        capacity_checker: Optional[CapacityChecker] = None,
    ):
        self.components = components
        self.all_loads = all_loads
        self.affected_loads = affected_loads
        self.load_map = {l.id: l for l in all_loads}
        self.failed_components = failed_components
        self.routes_by_load = routes_by_load
        self.capacity_checker = capacity_checker or CapacityChecker(components)

    def generate_and_rank_strategies(self) -> List[StrategyResult]:
        """
        Generates diverse candidate strategies, evaluates their performance metrics,
        and ranks them using multi-criteria hierarchical scoring.
        """
        if not self.affected_loads:
            return []

        optimizer = RestorationOptimizer(
            self.components,
            self.affected_loads,
            self.routes_by_load,
            self.capacity_checker,
        )

        candidate_configs = [
            (
                "STRAT-1-CRITICAL-FIRST",
                "Strategy A (Critical Load Priority & Safe Reserve Margin)",
                "CRITICAL_FIRST",
                None,
            ),
            (
                "STRAT-2-MAX-DEMAND",
                "Strategy B (Maximum Total Demand Restored)",
                "MAX_DEMAND",
                None,
            ),
            (
                "STRAT-3-MIN-SWITCHING",
                "Strategy C (Minimal Switching & Rapid Response)",
                "MIN_SWITCHING",
                None,
            ),
        ]

        evaluated_strategies: List[StrategyResult] = []
        seen_route_signatures: Set[str] = set()

        for strat_id, name, profile, excl_routes in candidate_configs:
            solve_res = optimizer.solve(profile=profile, excluded_route_ids=excl_routes)

            if solve_res["status"] not in (RestorationStatus.OPTIMAL, RestorationStatus.FEASIBLE):
                continue

            selected_routes = solve_res["selected_routes"]
            # Create unique signature of active routes: (load_id: route_id)
            signature = "|".join(
                f"{lid}:{selected_routes[lid].route_id}" for lid in sorted(selected_routes.keys())
            )

            # Record if unique or add distinctive tag
            is_unique = signature not in seen_route_signatures
            seen_route_signatures.add(signature)

            # Extract metrics
            restored_ids = solve_res["restored_load_ids"]
            unserved_ids = solve_res["unserved_load_ids"]
            restored_loads = [self.load_map[lid] for lid in restored_ids if lid in self.load_map]

            # Critical loads summary
            crit_affected = [l for l in self.affected_loads if l.is_critical]
            crit_restored = [l for l in crit_affected if l.id in restored_ids]
            crit_pct = (len(crit_restored) / len(crit_affected) * 100.0) if crit_affected else 100.0

            crit_summary = CriticalLoadsSummary(
                total_critical=len(crit_affected),
                restored_critical=len(crit_restored),
                unserved_critical=len(crit_affected) - len(crit_restored),
                restored_percentage=round(crit_pct, 2),
                critical_loads_details=[
                    {"id": l.id, "name": l.name, "restored": l.id in restored_ids, "demand_mw": l.demand_mw}
                    for l in crit_affected
                ],
            )

            # Impact analysis
            impact = ImpactCalculator.calculate_impact(
                affected_loads=self.affected_loads,
                restored_load_ids=restored_ids,
                all_loads=self.all_loads,
            )

            # Capacity metrics
            util_summary = solve_res["component_utilization"]
            feeder_utils = util_summary.get("feeders", [])
            transformer_utils = util_summary.get("transformers", [])

            max_feeder_util = max((u.utilization_pct for u in feeder_utils), default=0.0)
            max_trans_util = max((u.utilization_pct for u in transformer_utils), default=0.0)

            # Recovery sequence
            sequence = RecoverySequenceGenerator.generate_sequence(
                failed_components=self.failed_components,
                selected_routes=selected_routes,
                restored_loads=restored_loads,
            )

            # Explanation
            explanation = (
                f"{name}: Restores {crit_summary.restored_percentage:.1f}% critical loads "
                f"({crit_summary.restored_critical}/{crit_summary.total_critical}), "
                f"reduces disruption by {impact.disruption_reduction_pct:.1f}% "
                f"({impact.restored_demand_mw:.2f} MW restored), "
                f"with max feeder utilization at {max_feeder_util:.1f}% and transformer at {max_trans_util:.1f}%."
            )

            strategy_obj = StrategyResult(
                strategy_id=strat_id,
                name=name,
                objective_score=solve_res["objective_value"],
                rank=0,  # Will be set during sorting
                restored_load_ids=restored_ids,
                unserved_load_ids=unserved_ids,
                selected_routes={lid: r.route_id for lid, r in selected_routes.items()},
                critical_loads_summary=crit_summary,
                impact=impact,
                max_feeder_utilization_pct=round(max_feeder_util, 2),
                max_transformer_utilization_pct=round(max_trans_util, 2),
                recovery_sequence=sequence,
                is_feasible=solve_res["is_capacity_valid"],
                explanation=explanation,
            )

            # If duplicate signature, keep if unique or if it's the primary strategy
            if is_unique or strat_id == "STRAT-1-CRITICAL-FIRST":
                evaluated_strategies.append(strategy_obj)

        # Generate Pareto alternative if fewer than 2 strategies
        if len(evaluated_strategies) == 1 and evaluated_strategies[0].selected_routes:
            primary_routes = set(evaluated_strategies[0].selected_routes.values())
            alt_solve = optimizer.solve(
                profile="CRITICAL_FIRST", excluded_route_ids=primary_routes
            )
            if alt_solve["status"] in (RestorationStatus.OPTIMAL, RestorationStatus.FEASIBLE):
                alt_selected_routes = alt_solve["selected_routes"]
                alt_restored_ids = alt_solve["restored_load_ids"]
                alt_restored_loads = [self.load_map[lid] for lid in alt_restored_ids if lid in self.load_map]

                crit_affected = [l for l in self.affected_loads if l.is_critical]
                crit_restored = [l for l in crit_affected if l.id in alt_restored_ids]
                crit_pct = (len(crit_restored) / len(crit_affected) * 100.0) if crit_affected else 100.0

                crit_summary = CriticalLoadsSummary(
                    total_critical=len(crit_affected),
                    restored_critical=len(crit_restored),
                    unserved_critical=len(crit_affected) - len(crit_restored),
                    restored_percentage=round(crit_pct, 2),
                )

                impact = ImpactCalculator.calculate_impact(
                    affected_loads=self.affected_loads,
                    restored_load_ids=alt_restored_ids,
                    all_loads=self.all_loads,
                )

                alt_util = alt_solve["component_utilization"]
                max_f = max((u.utilization_pct for u in alt_util.get("feeders", [])), default=0.0)
                max_t = max((u.utilization_pct for u in alt_util.get("transformers", [])), default=0.0)

                alt_seq = RecoverySequenceGenerator.generate_sequence(
                    self.failed_components, alt_selected_routes, alt_restored_loads
                )

                evaluated_strategies.append(
                    StrategyResult(
                        strategy_id="STRAT-ALT-PARETO",
                        name="Strategy D (Alternative Rerouting Configuration)",
                        objective_score=alt_solve["objective_value"],
                        rank=0,
                        restored_load_ids=alt_restored_ids,
                        unserved_load_ids=alt_solve["unserved_load_ids"],
                        selected_routes={lid: r.route_id for lid, r in alt_selected_routes.items()},
                        critical_loads_summary=crit_summary,
                        impact=impact,
                        max_feeder_utilization_pct=round(max_f, 2),
                        max_transformer_utilization_pct=round(max_t, 2),
                        recovery_sequence=alt_seq,
                        is_feasible=alt_solve["is_capacity_valid"],
                        explanation=(
                            f"Alternative Rerouting Configuration: Restores {crit_pct:.1f}% critical loads, "
                            f"{impact.disruption_reduction_pct:.1f}% disruption reduction."
                        ),
                    )
                )

        # Multi-Criteria Strategy Ranking Logic:
        # 1. Feasibility (True > False)
        # 2. Critical Load Restored % (100% highest)
        # 3. Disruption Reduction % (Higher is better)
        # 4. Max Feeder Utilization (Lower peak load is safer)
        # 5. Number of recovery sequence actions (Fewer is simpler)
        ranked_strategies = sorted(
            evaluated_strategies,
            key=lambda s: (
                not s.is_feasible,
                -s.critical_loads_summary.restored_percentage,
                -s.impact.disruption_reduction_pct,
                s.max_feeder_utilization_pct,
                len(s.recovery_sequence),
            ),
        )

        # Assign integer ranks
        for idx, strat in enumerate(ranked_strategies, start=1):
            strat.rank = idx

        return ranked_strategies
