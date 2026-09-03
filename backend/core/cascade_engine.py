"""
CascadeEngine - Analyzes cascade failure scenarios in the grid.

Simulates the propagation of failures through the network:
1. Component fails
2. Recalculate active topology
3. Identify disconnected components
4. Estimate load redistribution
5. Detect capacity violations (overloads)
6. Identify vulnerable assets
7. Identify critical facilities at risk
8. Generate ordered cascade events
"""

from typing import List, Dict, Set
from models.grid_schemas import CascadeEvent
from core.grid_engine import GridDigitalTwin


class CascadeEngine:
    """
    Analyzes cascade failure and secondary effects.
    
    Given an initial failure, simulates how cascading overloads,
    supply loss, and network reconfiguration propagate through the grid.
    """
    
    def __init__(self, grid: GridDigitalTwin):
        """
        Initialize CascadeEngine.
        
        Args:
            grid: GridDigitalTwin instance
        """
        self.grid = grid
    
    def analyze_cascade(self, failed_component_id: str) -> List[CascadeEvent]:
        """
        Analyze cascade failure for a given component.
        
        Args:
            failed_component_id: ID of initially failed component
            
        Returns:
            Ordered list of cascade events
        """
        events: List[CascadeEvent] = []
        step = 1
        
        # Step 1: Mark failed component
        node = self.grid.get_component(failed_component_id)
        if not node:
            return events
        
        comp_name = node.get("name", failed_component_id)
        events.append(CascadeEvent(
            step=step,
            component=failed_component_id,
            event="FAILED",
            reason=f"Initial physical trip on {comp_name}"
        ))
        step += 1
        
        # Step 2: Apply scenario and read physical states
        scenario = self.grid.apply_failure_scenario(failed_component_id)
        
        disconnected = scenario.get("disconnected", [])
        for comp_id in disconnected:
            if comp_id == failed_component_id:
                continue
            events.append(CascadeEvent(
                step=step,
                component=comp_id,
                event="DISCONNECTED",
                reason=f"Downstream path lost due to {failed_component_id} outage"
            ))
            step += 1
        
        # Step 3: Critical facility status
        critical_facilities = self.grid.identify_critical_facilities()
        for crit_id in critical_facilities:
            if crit_id == failed_component_id:
                continue
            crit_node = self.grid.get_component(crit_id)
            if not crit_node:
                continue
            c_status = crit_node.get("status")
            if c_status in ["critical_risk", "disconnected"]:
                events.append(CascadeEvent(
                    step=step,
                    component=crit_id,
                    event="SUPPLY_LOST",
                    reason="Critical healthcare power lost - no energized source available"
                ))
                step += 1
            elif c_status in ["at_risk", "warning", "overloaded"]:
                events.append(CascadeEvent(
                    step=step,
                    component=crit_id,
                    event="SUPPLY_AT_RISK",
                    reason="Primary feed interrupted - reliant on alternate feeder capacity"
                ))
                step += 1
        
        # Step 4: Overloaded / Warning components
        overloaded = scenario.get("overloaded", [])
        for comp_id in overloaded:
            if comp_id == failed_component_id:
                continue
            load_pct = self.grid.calculate_load_percentage(comp_id)
            events.append(CascadeEvent(
                step=step,
                component=comp_id,
                event="OVERLOADED",
                reason=f"Rerouted power flow caused {load_pct:.1f}% capacity utilization"
            ))
            step += 1
            
        warnings = scenario.get("warning", [])
        for comp_id in warnings:
            if comp_id == failed_component_id or comp_id in overloaded or comp_id in critical_facilities:
                continue
            load_pct = self.grid.calculate_load_percentage(comp_id)
            events.append(CascadeEvent(
                step=step,
                component=comp_id,
                event="WARNING",
                reason=f"Operating under elevated loading: {load_pct:.1f}% utilization"
            ))
            step += 1
        
        return events
    
    def get_secondary_vulnerabilities(
        self,
        failed_component_id: str
    ) -> Dict[str, List[str]]:
        """
        Identify secondary vulnerable assets after cascade.
        """
        scenario = self.grid.apply_failure_scenario(failed_component_id)
        critical_facilities = self.grid.identify_critical_facilities()
        at_risk_critical = [
            c for c in critical_facilities
            if self.grid.get_component_status(c) in ["critical_risk", "at_risk", "disconnected", "warning"]
            and c != failed_component_id
        ]
        
        return {
            "overloaded": scenario.get("overloaded", []),
            "disconnected": scenario.get("disconnected", []),
            "at_risk_critical": at_risk_critical
        }
