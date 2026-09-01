"""
Feeder and Transformer Capacity Validation for GridTwin Restoration.

Responsibilities:
- Validate that proposed candidate routes do not violate rated thermal limits of feeders or transformers.
- Calculate post-restoration load, utilization %, capacity margin (MW), and margin %.
- Strictly prevent secondary overloads and cascading failures.
- Provide component-level diagnostics for visualization and strategy evaluation.
"""

from typing import List, Dict, Tuple, Optional, Set
from restoration.models import (
    GridComponent,
    CandidateRoute,
    ComponentUtilization,
    ComponentType,
    ComponentStatus,
)
from restoration.exceptions import CapacityViolationError


class CapacityChecker:
    """
    Validates physical thermal capacity constraints on distribution feeders and step-down transformers.
    """

    def __init__(self, components: List[GridComponent]):
        self.components: Dict[str, GridComponent] = {c.id: c for c in components}
        self.feeders: Dict[str, GridComponent] = {
            c.id: c for c in components if c.type == ComponentType.FEEDER
        }
        self.transformers: Dict[str, GridComponent] = {
            c.id: c for c in components if c.type == ComponentType.TRANSFORMER
        }

    def evaluate_route_set_capacity(
        self,
        selected_routes: List[CandidateRoute],
        load_demands: Dict[str, float],
        failed_components: Optional[List[str]] = None,
    ) -> Tuple[bool, Dict[str, List[ComponentUtilization]], List[str]]:
        """
        Evaluates the combined thermal loading across all feeders and transformers
        when the given set of candidate routes is energized simultaneously.

        Args:
            selected_routes: List of activated CandidateRoute objects.
            load_demands: Dict mapping load_id -> demand_mw.
            failed_components: Optional list of failed component IDs.

        Returns:
            (is_feasible, utilization_summary_dict, violation_reasons)
        """
        failed_set = set(failed_components or [])
        # Track incremental loading added to each component
        added_load_by_component: Dict[str, float] = {}

        for route in selected_routes:
            demand = load_demands.get(route.load_id, route.estimated_added_load_mw)
            # Add demand to all feeders and transformers used in this route
            for f_id in route.feeders_used:
                added_load_by_component[f_id] = added_load_by_component.get(f_id, 0.0) + demand
            for t_id in route.transformers_used:
                added_load_by_component[t_id] = added_load_by_component.get(t_id, 0.0) + demand

        is_feasible = True
        violation_reasons: List[str] = []
        feeder_utilizations: List[ComponentUtilization] = []
        transformer_utilizations: List[ComponentUtilization] = []

        # 1. Evaluate Feeders
        for f_id, feeder in self.feeders.items():
            added_mw = added_load_by_component.get(f_id, 0.0)
            base_mw = feeder.base_load_mw
            new_load_mw = base_mw + added_mw
            capacity_mw = feeder.capacity_mw
            utilization_pct = (new_load_mw / capacity_mw * 100) if capacity_mw > 0 else 0.0
            margin_mw = capacity_mw - new_load_mw
            margin_pct = (margin_mw / capacity_mw * 100) if capacity_mw > 0 else 0.0

            if f_id in failed_set or feeder.status == ComponentStatus.FAILED:
                status = "FAILED / ISOLATED"
            elif new_load_mw > capacity_mw + 1e-4:
                is_feasible = False
                status = "OVERLOADED"
                violation_reasons.append(
                    f"Feeder '{f_id}' capacity exceeded: {new_load_mw:.2f} MW / {capacity_mw:.2f} MW ({utilization_pct:.1f}%)"
                )
            else:
                status = "FEASIBLE"

            feeder_utilizations.append(
                ComponentUtilization(
                    id=f_id,
                    name=feeder.name,
                    type=ComponentType.FEEDER,
                    capacity_mw=capacity_mw,
                    base_load_mw=base_mw,
                    added_restoration_load_mw=added_mw,
                    post_restoration_load_mw=new_load_mw,
                    utilization_pct=round(utilization_pct, 2),
                    margin_mw=round(margin_mw, 3),
                    margin_pct=round(margin_pct, 2),
                    status=status,
                )
            )

        # 2. Evaluate Transformers
        for t_id, transformer in self.transformers.items():
            added_mw = added_load_by_component.get(t_id, 0.0)
            base_mw = transformer.base_load_mw
            new_load_mw = base_mw + added_mw
            capacity_mw = transformer.capacity_mw
            utilization_pct = (new_load_mw / capacity_mw * 100) if capacity_mw > 0 else 0.0
            margin_mw = capacity_mw - new_load_mw
            margin_pct = (margin_mw / capacity_mw * 100) if capacity_mw > 0 else 0.0

            if t_id in failed_set or transformer.status == ComponentStatus.FAILED:
                status = "FAILED / ISOLATED"
            elif new_load_mw > capacity_mw + 1e-4:
                is_feasible = False
                status = "OVERLOADED"
                violation_reasons.append(
                    f"Transformer '{t_id}' capacity exceeded: {new_load_mw:.2f} MW / {capacity_mw:.2f} MW ({utilization_pct:.1f}%)"
                )
            else:
                status = "FEASIBLE"

            transformer_utilizations.append(
                ComponentUtilization(
                    id=t_id,
                    name=transformer.name,
                    type=ComponentType.TRANSFORMER,
                    capacity_mw=capacity_mw,
                    base_load_mw=base_mw,
                    added_restoration_load_mw=added_mw,
                    post_restoration_load_mw=new_load_mw,
                    utilization_pct=round(utilization_pct, 2),
                    margin_mw=round(margin_mw, 3),
                    margin_pct=round(margin_pct, 2),
                    status=status,
                )
            )

        summary = {
            "feeders": feeder_utilizations,
            "transformers": transformer_utilizations,
        }

        return is_feasible, summary, violation_reasons

    def check_single_route_headroom(self, route: CandidateRoute, demand_mw: float) -> Tuple[bool, str]:
        """
        Checks if an individual candidate route has sufficient headroom across all its elements.
        """
        for f_id in route.feeders_used:
            feeder = self.feeders.get(f_id)
            if feeder and (feeder.base_load_mw + demand_mw > feeder.capacity_mw + 1e-4):
                return False, f"Feeder {f_id} has insufficient headroom ({feeder.capacity_mw - feeder.base_load_mw:.2f} MW available < {demand_mw:.2f} MW required)"

        for t_id in route.transformers_used:
            transformer = self.transformers.get(t_id)
            if transformer and (transformer.base_load_mw + demand_mw > transformer.capacity_mw + 1e-4):
                return False, f"Transformer {t_id} has insufficient headroom ({transformer.capacity_mw - transformer.base_load_mw:.2f} MW available < {demand_mw:.2f} MW required)"

        return True, "Headroom available"
