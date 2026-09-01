"""
Google OR-Tools CP-SAT Restoration Optimizer for GridTwin.

Responsibilities:
- Mathematically formulate the grid restoration problem as a pure-integer Linear Program in CP-SAT.
- Respect feeder and transformer thermal limits without non-linear approximations.
- Prioritize critical facilities (Hospitals, Emergency Centers) over general loads.
- Maximize reserve capacity margin and minimize route switching hops.
- Produce mathematically verified optimal and feasible restoration solutions.
"""

from typing import List, Dict, Tuple, Optional, Set, Any
from ortools.sat.python import cp_model
from restoration.models import (
    GridComponent,
    LoadDemand,
    CandidateRoute,
    ComponentType,
    RestorationStatus,
)
from restoration.capacity_checker import CapacityChecker


class RestorationOptimizer:
    """
    CP-SAT Combinatorial Optimization Engine for Grid Restoration.
    """

    SCALE_FACTOR: int = 1000  # 1.0 MW = 1000 kW (Integer Scaling)

    def __init__(
        self,
        components: List[GridComponent],
        affected_loads: List[LoadDemand],
        candidate_routes_by_load: Dict[str, List[CandidateRoute]],
        capacity_checker: Optional[CapacityChecker] = None,
    ):
        self.components = components
        self.component_map = {c.id: c for c in components}
        self.affected_loads = affected_loads
        self.load_map = {l.id: l for l in affected_loads}
        self.routes_by_load = candidate_routes_by_load
        self.capacity_checker = capacity_checker or CapacityChecker(components)

    def solve(
        self,
        profile: str = "CRITICAL_FIRST",
        w_critical: int = 1000,
        w_regular: int = 10,
        w_margin: int = 1,
        w_switch: int = 50,
        excluded_route_ids: Optional[Set[str]] = None,
        time_limit_sec: float = 10.0,
    ) -> Dict[str, Any]:
        """
        Builds and solves the CP-SAT restoration model.

        Returns a structured dictionary containing:
        - status: OPTIMAL | FEASIBLE | INFEASIBLE | NO_FEASIBLE_RESTORATION
        - objective_value: float
        - restored_load_ids: List[str]
        - unserved_load_ids: List[str]
        - selected_routes: Dict[load_id, CandidateRoute]
        - component_utilization: Dict[str, List[ComponentUtilization]]
        - diagnostics: Dict
        """
        # If no affected loads, trivial return
        if not self.affected_loads:
            return {
                "status": RestorationStatus.OPTIMAL,
                "objective_value": 0.0,
                "restored_load_ids": [],
                "unserved_load_ids": [],
                "selected_routes": {},
                "component_utilization": self.capacity_checker.evaluate_route_set_capacity([], {})[1],
                "diagnostics": {"message": "No affected loads to restore"},
            }

        # Check if any routes exist at all
        total_routes_count = sum(len(routes) for routes in self.routes_by_load.values())
        if total_routes_count == 0:
            return {
                "status": RestorationStatus.NO_FEASIBLE_RESTORATION,
                "objective_value": 0.0,
                "restored_load_ids": [],
                "unserved_load_ids": [l.id for l in self.affected_loads],
                "selected_routes": {},
                "component_utilization": self.capacity_checker.evaluate_route_set_capacity([], {})[1],
                "diagnostics": {"reason": "No alternate paths exist connecting operational substations to affected loads"},
            }

        # Adjust weights based on preset profiles
        if profile == "MAX_DEMAND":
            w_critical = 100
            w_regular = 100
            w_margin = 0
            w_switch = 10
        elif profile == "MIN_SWITCHING":
            w_critical = 1000
            w_regular = 10
            w_margin = 1
            w_switch = 500
        elif profile == "CRITICAL_FIRST":
            w_critical = 1000
            w_regular = 10
            w_margin = 5
            w_switch = 50

        model = cp_model.CpModel()

        # 1. Decision Variables
        # x[load_id, route_id] in {0, 1}
        x_vars: Dict[Tuple[str, str], cp_model.IntVar] = {}
        # y[load_id] in {0, 1}
        y_vars: Dict[str, cp_model.IntVar] = {}

        for load in self.affected_loads:
            y_vars[load.id] = model.NewBoolVar(f"restore_{load.id}")
            routes = self.routes_by_load.get(load.id, [])
            for r in routes:
                x_vars[(load.id, r.route_id)] = model.NewBoolVar(f"x_{load.id}_{r.route_id}")

        # 2. Hard Constraints

        # Constraint 1: Restoration-Route Linkage
        # sum(x[load, route]) == y[load]
        for load in self.affected_loads:
            routes = self.routes_by_load.get(load.id, [])
            if routes:
                model.Add(sum(x_vars[(load.id, r.route_id)] for r in routes) == y_vars[load.id])
            else:
                model.Add(y_vars[load.id] == 0)

        # Constraint 2: Feeder and Transformer Capacity Bounds
        # load_e = base_load_e + sum(demand_l * x[l, r] for l, r using e) <= capacity_e
        load_vars: Dict[str, cp_model.IntVar] = {}
        margin_vars: Dict[str, cp_model.IntVar] = {}

        monitored_components = [
            c for c in self.components if c.type in (ComponentType.FEEDER, ComponentType.TRANSFORMER)
        ]

        for comp in monitored_components:
            cap_int = int(comp.capacity_mw * self.SCALE_FACTOR)
            base_int = int(comp.base_load_mw * self.SCALE_FACTOR)

            # Variable for post-restoration load
            load_var = model.NewIntVar(0, cap_int, f"load_{comp.id}")
            margin_var = model.NewIntVar(0, cap_int, f"margin_{comp.id}")

            load_vars[comp.id] = load_var
            margin_vars[comp.id] = margin_var

            # Gather incoming added restoration demand on this component
            added_terms = []
            for load in self.affected_loads:
                demand_int = int(load.demand_mw * self.SCALE_FACTOR)
                routes = self.routes_by_load.get(load.id, [])
                for r in routes:
                    uses_comp = False
                    if comp.type == ComponentType.FEEDER and comp.id in r.feeders_used:
                        uses_comp = True
                    elif comp.type == ComponentType.TRANSFORMER and comp.id in r.transformers_used:
                        uses_comp = True

                    if uses_comp:
                        added_terms.append(demand_int * x_vars[(load.id, r.route_id)])

            if added_terms:
                model.Add(load_var == base_int + sum(added_terms))
            else:
                model.Add(load_var == base_int)

            # Capacity margin definition: margin_e = capacity_e - load_e
            model.Add(margin_var == cap_int - load_var)

        # Constraint 3: Pareto Diversity Exclusion (for alternative strategy generation)
        if excluded_route_ids and len(excluded_route_ids) > 0:
            active_excluded_vars = [
                var for key, var in x_vars.items() if key[1] in excluded_route_ids
            ]
            if active_excluded_vars:
                model.Add(sum(active_excluded_vars) <= len(active_excluded_vars) - 1)

        # 3. Pure Linear Multi-Objective Function
        obj_terms = []

        for load in self.affected_loads:
            demand_int = int(load.demand_mw * self.SCALE_FACTOR)
            priority_val = load.priority  # 1 to 100

            if load.is_critical:
                # Critical load weighted heavily
                obj_terms.append(w_critical * priority_val * demand_int * y_vars[load.id])
            else:
                # Regular load weighted moderately
                obj_terms.append(w_regular * priority_val * demand_int * y_vars[load.id])

            # Hop/Switching penalty
            routes = self.routes_by_load.get(load.id, [])
            for r in routes:
                hops_val = r.total_hops
                obj_terms.append(-w_switch * hops_val * x_vars[(load.id, r.route_id)])

        # Margin bonus across all monitored components
        if w_margin > 0:
            for comp in monitored_components:
                obj_terms.append(w_margin * margin_vars[comp.id])

        model.Maximize(sum(obj_terms))

        # 4. Solver Execution
        solver = cp_model.CpSolver()
        solver.parameters.max_time_in_seconds = time_limit_sec
        status = solver.Solve(model)

        if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            restoration_status = (
                RestorationStatus.OPTIMAL if status == cp_model.OPTIMAL else RestorationStatus.FEASIBLE
            )

            restored_load_ids: List[str] = []
            unserved_load_ids: List[str] = []
            selected_routes: Dict[str, CandidateRoute] = {}
            active_routes_list: List[CandidateRoute] = []

            for load in self.affected_loads:
                if solver.Value(y_vars[load.id]) == 1:
                    restored_load_ids.append(load.id)
                    routes = self.routes_by_load.get(load.id, [])
                    for r in routes:
                        if solver.Value(x_vars[(load.id, r.route_id)]) == 1:
                            selected_routes[load.id] = r
                            active_routes_list.append(r)
                            break
                else:
                    unserved_load_ids.append(load.id)

            # Evaluate exact capacity utilization metrics using CapacityChecker
            load_demands = {l.id: l.demand_mw for l in self.affected_loads}
            is_valid, util_summary, violations = self.capacity_checker.evaluate_route_set_capacity(
                active_routes_list, load_demands
            )

            return {
                "status": restoration_status,
                "objective_value": solver.ObjectiveValue(),
                "restored_load_ids": restored_load_ids,
                "unserved_load_ids": unserved_load_ids,
                "selected_routes": selected_routes,
                "component_utilization": util_summary,
                "is_capacity_valid": is_valid,
                "violations": violations,
                "diagnostics": {
                    "wall_time": solver.WallTime(),
                    "user_time": solver.UserTime(),
                    "num_branches": solver.NumBranches(),
                },
            }
        else:
            return {
                "status": RestorationStatus.INFEASIBLE,
                "objective_value": 0.0,
                "restored_load_ids": [],
                "unserved_load_ids": [l.id for l in self.affected_loads],
                "selected_routes": {},
                "component_utilization": self.capacity_checker.evaluate_route_set_capacity([], {})[1],
                "diagnostics": {
                    "reason": "CP-SAT solver found no feasible solution satisfying all capacity limits",
                    "solver_status": solver.StatusName(status),
                },
            }
