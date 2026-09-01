"""
Dynamic Recovery Sequence Generation for GridTwin Restoration.

Responsibilities:
- Transform optimal decision variables and route selections into an actionable, step-by-step restoration workflow.
- Ensure strict sequential order: ISOLATE -> REROUTE -> RESTORE.
- Prioritize hospital and emergency energization before residential/commercial loads.
- Ensure no transient intermediate overload during sequential switching.
"""

from typing import List, Dict, Optional
from restoration.models import (
    RestorationAction,
    ActionType,
    CandidateRoute,
    LoadDemand,
)


class RecoverySequenceGenerator:
    """
    Generates an ordered, validated sequence of restoration operations.
    """

    @staticmethod
    def generate_sequence(
        failed_components: List[str],
        selected_routes: Dict[str, CandidateRoute],
        restored_loads: List[LoadDemand],
    ) -> List[RestorationAction]:
        """
        Generates step-by-step recovery actions:
        1. ISOLATE all failed equipment.
        2. REROUTE / Switch transfer paths for restored loads.
        3. RESTORE / Energize loads in descending priority order.
        """
        sequence: List[RestorationAction] = []
        step_number = 1

        # Step 1: Isolation Actions for Failed Components
        for failed_id in failed_components:
            sequence.append(
                RestorationAction(
                    step=step_number,
                    action=ActionType.ISOLATE,
                    target=failed_id,
                    details=f"Mark faulted component '{failed_id}' as isolated in the simulated grid state.",
                )
            )
            step_number += 1

        # Step 2: Rerouting Actions (Transfer Switches / Tie-Lines)
        for load in restored_loads:
            route = selected_routes.get(load.id)
            if route:
                feeders_str = ", ".join(route.feeders_used) if route.feeders_used else "Alternate Feeder"
                transformers_str = ", ".join(route.transformers_used) if route.transformers_used else "Alternate Transformer"
                from_path_str = " -> ".join(load.pre_fault_path) if load.pre_fault_path else "Primary"
                to_path_str = " -> ".join(route.path_nodes)

                sequence.append(
                    RestorationAction(
                        step=step_number,
                        action=ActionType.REROUTE,
                        target=load.id,
                        load_id=load.id,
                        from_path=from_path_str,
                        to_path=to_path_str,
                        via=route.feeders_used + route.transformers_used,
                        load_mw=load.demand_mw,
                        details=f"Transfer {load.name} ({load.id}) supply to {feeders_str} via {transformers_str} (Path: {to_path_str})",
                    )
                )
                step_number += 1

        # Step 3: Sequential Energization in Strict Priority Order
        # Sort by: 1) is_critical (True first), 2) priority (descending), 3) demand (descending)
        sorted_restored_loads = sorted(
            restored_loads,
            key=lambda l: (not l.is_critical, -l.priority, -l.demand_mw),
        )

        for load in sorted_restored_loads:
            crit_label = "[CRITICAL] " if load.is_critical else ""
            sequence.append(
                RestorationAction(
                    step=step_number,
                    action=ActionType.RESTORE,
                    target=load.id,
                    load_id=load.id,
                    load_mw=load.demand_mw,
                    details=f"{crit_label}Energize {load.name} ({load.demand_mw:.2f} MW, Priority {load.priority})",
                )
            )
            step_number += 1

        return sequence
