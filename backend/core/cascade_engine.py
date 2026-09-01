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
        if not self.grid.get_component(failed_component_id):
            return events
        
        events.append(CascadeEvent(
            step=step,
            component=failed_component_id,
            event="FAILED",
            reason="Initial failure event"
        ))
        step += 1
        
        # Step 2: Find affected components (disconnected by the failure)
        affected = self.grid.get_affected_components(failed_component_id)
        
        for comp_id in affected:
            events.append(CascadeEvent(
                step=step,
                component=comp_id,
                event="DISCONNECTED",
                reason=f"No longer reachable due to {failed_component_id} failure"
            ))
            step += 1
        
        # Step 3: Identify critical facilities at risk
        critical_facilities = self.grid.identify_critical_facilities()
        critical_at_risk = [c for c in critical_facilities if c in affected]
        
        for crit_id in critical_at_risk:
            events.append(CascadeEvent(
                step=step,
                component=crit_id,
                event="SUPPLY_AT_RISK",
                reason="Critical facility supply at risk"
            ))
            step += 1
        
        # Step 4: Detect capacity violations (overloads)
        # Simulate load redistribution - affected load now tries to reroute
        # through alternative paths, potentially overloading other components
        overloaded = self._detect_overloaded_components(
            failed_component_id,
            affected
        )
        
        for comp_id in overloaded:
            load_pct = self.grid.calculate_load_percentage(comp_id)
            events.append(CascadeEvent(
                step=step,
                component=comp_id,
                event="OVERLOADED",
                reason=f"Capacity violation: {load_pct:.1f}% utilization"
            ))
            step += 1
        
        return events
    
    def _detect_overloaded_components(
        self,
        failed_component_id: str,
        affected: List[str]
    ) -> List[str]:
        """
        Heuristically detect components that would be overloaded.
        
        This is a simplified model: components adjacent to failed/affected
        nodes that now carry rerouted load.
        
        Args:
            failed_component_id: The initially failed component
            affected: List of now-disconnected components
            
        Returns:
            List of potentially overloaded component IDs
        """
        overloaded = []
        
        # Get upstream components (that might now have extra load)
        # These are components that have edges pointing to affected nodes
        for affected_id in affected:
            # Find incoming edges to affected component
            predecessors = list(self.grid.graph.predecessors(affected_id))
            for pred in predecessors:
                if pred != failed_component_id:
                    load_pct = self.grid.calculate_load_percentage(pred)
                    # Consider overloaded if > 80% capacity
                    if load_pct > 80.0 and pred not in overloaded:
                        overloaded.append(pred)
        
        return overloaded
    
    def get_secondary_vulnerabilities(
        self,
        failed_component_id: str
    ) -> Dict[str, List[str]]:
        """
        Identify secondary vulnerable assets after cascade.
        
        Returns categorized vulnerable components.
        
        Args:
            failed_component_id: ID of failed component
            
        Returns:
            Dict with categories:
                - overloaded: Components with >80% utilization
                - disconnected: Components with no supply path
                - at_risk: Critical facilities threatened
        """
        affected = self.grid.get_affected_components(failed_component_id)
        overloaded = self._detect_overloaded_components(failed_component_id, affected)
        critical_facilities = self.grid.identify_critical_facilities()
        at_risk_critical = [c for c in critical_facilities if c in affected]
        
        return {
            "overloaded": overloaded,
            "disconnected": affected,
            "at_risk_critical": at_risk_critical
        }
