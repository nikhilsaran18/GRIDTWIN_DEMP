"""
GridDigitalTwin - Digital twin of the power grid using NetworkX.

Manages grid state, component status, connectivity, and provides query operations.
Independent from FastAPI and frontend - can be used by any service layer.
"""

import json
import copy
from pathlib import Path
from typing import List, Dict, Optional, Set, Tuple
import networkx as nx
from models.grid_schemas import (
    NodeSchema,
    EdgeSchema,
    GridSummary,
    GridResponse,
)


class GridDigitalTwin:
    """
    NetworkX-based digital twin of the power grid.
    
    Manages:
    - Component state (nodes)
    - Connection state (edges)
    - Graph topology and connectivity
    - Component failure and recovery
    - Load calculation and redistribution
    """
    
    def __init__(self, dataset_path: Optional[str] = None):
        """
        Initialize GridDigitalTwin.
        
        Args:
            dataset_path: Path to grid.json. If None, loads from default location.
        """
        self.graph = nx.DiGraph()
        self._node_data: Dict[str, dict] = {}
        self._edge_data: Dict[str, dict] = {}
        self._baseline_node_data: Dict[str, dict] = {}
        self._baseline_edge_data: Dict[str, dict] = {}
        
        if dataset_path is None:
            dataset_path = Path(__file__).parent.parent / "data" / "grid.json"
        else:
            dataset_path = Path(dataset_path)
            
        self._load_dataset(dataset_path)
    
    def _load_dataset(self, path: Path) -> None:
        """Load grid dataset from JSON file."""
        if not path.exists():
            raise FileNotFoundError(f"Grid dataset not found: {path}")
        
        with open(path, 'r') as f:
            data = json.load(f)
        
        # Load nodes
        for node_data in data.get("nodes", []):
            node_id = node_data["id"]
            self._node_data[node_id] = copy.deepcopy(node_data)
            self.graph.add_node(
                node_id,
                **node_data
            )
        
        # Load edges
        for edge_data in data.get("edges", []):
            source = edge_data["source"]
            target = edge_data["target"]
            edge_id = edge_data["id"]
            self._edge_data[edge_id] = copy.deepcopy(edge_data)
            self.graph.add_edge(
                source,
                target,
                edge_id=edge_id,
                **edge_data
            )
        
        # Store baseline for reset
        self._baseline_node_data = copy.deepcopy(self._node_data)
        self._baseline_edge_data = copy.deepcopy(self._edge_data)
    
    def get_component(self, component_id: str) -> Optional[Dict]:
        """Get component by ID."""
        return self._node_data.get(component_id)
    
    def get_component_status(self, component_id: str) -> Optional[str]:
        """Get status of a component."""
        node = self.get_component(component_id)
        if node:
            return node.get("status")
        return None
    
    def set_component_status(self, component_id: str, status: str) -> bool:
        """Set component status."""
        if component_id not in self._node_data:
            return False
        
        self._node_data[component_id]["status"] = status
        if self.graph.has_node(component_id):
            self.graph.nodes[component_id]["status"] = status
        return True
    
    def fail_component(self, component_id: str) -> bool:
        """Mark component as failed."""
        if component_id not in self._node_data:
            return False
        
        return self.set_component_status(component_id, "failed")
    
    def reset_grid(self) -> None:
        """Reset grid to baseline state."""
        self._node_data = copy.deepcopy(self._baseline_node_data)
        self._edge_data = copy.deepcopy(self._baseline_edge_data)
        
        # Rebuild graph
        self.graph.clear()
        for node_data in self._node_data.values():
            self.graph.add_node(node_data["id"], **node_data)
        
        for edge_data in self._edge_data.values():
            source = edge_data["source"]
            target = edge_data["target"]
            self.graph.add_edge(source, target, **edge_data)
    
    def calculate_connectivity(self, source: str) -> Set[str]:
        """
        Calculate all nodes reachable from source in current topology.
        
        Args:
            source: Starting node ID
            
        Returns:
            Set of reachable node IDs
        """
        reachable = set()
        try:
            failed = {
                node_id for node_id, data in self._node_data.items()
                if data.get("status") == "failed"
            }
            graph = self.graph.copy()
            graph.remove_nodes_from(failed - {source})
            if source in failed:
                return set()
            reachable = nx.descendants(graph, source)
            reachable.add(source)  # Include source itself
        except nx.NetworkXError:
            if source in self.graph:
                reachable = {source}
        
        return reachable
    
    def identify_disconnected_nodes(self) -> Dict[str, List[str]]:
        """
        Identify nodes disconnected from sources.
        
        Returns:
            Dict mapping node type to list of disconnected node IDs
        """
        sources = [
            node_id for node_id, data in self._node_data.items()
            if data.get("type") in ["source", "substation"] and data.get("status") != "failed"
        ]
        
        reachable = set()
        for source in sources:
            reachable.update(self.calculate_connectivity(source))
        
        all_nodes = set(self._node_data.keys())
        failed_nodes = {
            node_id for node_id, data in self._node_data.items()
            if data.get("status") == "failed"
        }
        disconnected = all_nodes - reachable - failed_nodes
        
        result = {}
        for node_id in disconnected:
            node_type = self._node_data[node_id].get("type", "unknown")
            if node_type not in result:
                result[node_type] = []
            result[node_type].append(node_id)
        
        return result
    
    def identify_critical_facilities(self) -> List[str]:
        """Get list of critical load IDs (hospitals, emergency services, etc.)."""
        return [
            node_id for node_id, data in self._node_data.items()
            if data.get("is_critical_load", False)
        ]
    
    def find_alternate_paths(
        self,
        source: str,
        target: str,
        max_length: int = 5
    ) -> List[List[str]]:
        """
        Find alternate paths from source to target.
        
        Args:
            source: Source node ID
            target: Target node ID
            max_length: Maximum path length to consider
            
        Returns:
            List of paths (each path is list of node IDs)
        """
        try:
            paths = list(
                nx.all_simple_paths(
                    self.graph,
                    source,
                    target,
                    cutoff=max_length
                )
            )
            return paths
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return []
    
    def calculate_load_percentage(self, component_id: str) -> float:
        """Calculate load percentage (0-100) for a component."""
        node = self.get_component(component_id)
        if not node:
            return 0.0
        
        capacity = node.get("capacity_mw", 1.0)
        if capacity <= 0:
            return 0.0
        
        load = node.get("load_mw", 0.0)
        percentage = (load / capacity) * 100.0
        return min(percentage, 200.0)
    
    def get_network_summary(self) -> GridSummary:
        """Get summary statistics of current grid state."""
        total = len(self._node_data)
        healthy = sum(
            1 for data in self._node_data.values()
            if data.get("status") == "normal"
        )
        failed = sum(
            1 for data in self._node_data.values()
            if data.get("status") == "failed"
        )
        at_risk = sum(
            1 for data in self._node_data.values()
            if data.get("status") in [
                "warning", "high_risk", "critical", "at_risk",
                "overloaded", "disconnected", "critical_risk"
            ]
        )
        
        total_load = sum(
            data.get("load_mw", 0.0) for data in self._node_data.values()
        )
        
        critical_loads = self.identify_critical_facilities()
        critical_at_risk = sum(
            1 for node_id in critical_loads
            if self._node_data[node_id].get("status") != "normal"
        )
        
        return GridSummary(
            total=total,
            healthy=healthy,
            at_risk=at_risk,
            failed=failed,
            total_load_mw=total_load,
            critical_loads_at_risk=critical_at_risk
        )
    
    def serialize(self) -> GridResponse:
        """
        Serialize current grid state to API response format.
        
        Returns:
            GridResponse with all nodes, edges, and summary
        """
        nodes = [
            NodeSchema(**data)
            for data in self._node_data.values()
        ]
        
        edges = [
            EdgeSchema(**data)
            for data in self._edge_data.values()
        ]
        
        summary = self.get_network_summary()
        
        return GridResponse(
            nodes=nodes,
            edges=edges,
            summary=summary
        )
    
    def get_failed_components(self) -> List[str]:
        """Get list of failed component IDs."""
        return [
            node_id for node_id, data in self._node_data.items()
            if data.get("status") == "failed"
        ]
    
    def get_affected_components(self, component_id: str) -> List[str]:
        """
        Get components affected by failure of given component.
        
        Args:
            component_id: ID of failed component
            
        Returns:
            List of affected component IDs (not including the failed one)
        """
        scenario = self.apply_failure_scenario(component_id)
        affected = set()
        affected.update(scenario.get("warning", []))
        affected.update(scenario.get("overloaded", []))
        affected.update(scenario.get("disconnected", []))
        return [c for c in affected if c != component_id]

    def apply_failure_scenario(self, component_id: str) -> Dict[str, List[str]]:
        """
        Apply physical/topological simulation of failure for component_id.
        Recalculates load redistribution, capacity utilization, node states, and edge states.
        
        Returns:
            Dict containing:
                - warning: list of component IDs in warning state
                - overloaded: list of component IDs in overloaded state
                - disconnected: list of disconnected component IDs
                - affected_edges: list of affected edge IDs
        """
        # Start from baseline
        self.reset_grid()
        
        if component_id not in self._node_data:
            return {"warning": [], "overloaded": [], "disconnected": [], "affected_edges": []}
        
        # Mark initial failed node
        self.set_component_status(component_id, "failed")
        
        warning_nodes = []
        overloaded_nodes = []
        disconnected_nodes = []
        affected_edges = []
        
        # S1 (Source Substation) Failure
        if component_id == "S1":
            # All downstream disconnected, H1 critical risk, no alternate source
            for node_id, data in self._node_data.items():
                if node_id == "S1":
                    continue
                if data.get("is_critical_load"):
                    data["status"] = "critical_risk"
                    data["load_mw"] = 0.0
                    disconnected_nodes.append(node_id)
                else:
                    data["status"] = "disconnected"
                    data["load_mw"] = 0.0
                    disconnected_nodes.append(node_id)
                self.graph.nodes[node_id]["status"] = data["status"]
            
            for edge_id, edge_data in self._edge_data.items():
                if edge_data["source"] == "S1":
                    edge_data["status"] = "failed"
                else:
                    edge_data["status"] = "disconnected"
                edge_data["load_mw"] = 0.0
                self.graph.edges[edge_data["source"], edge_data["target"]]["status"] = edge_data["status"]
                affected_edges.append(edge_id)
                
            return {
                "warning": warning_nodes,
                "overloaded": overloaded_nodes,
                "disconnected": disconnected_nodes,
                "affected_edges": affected_edges
            }
        
        # T7 (Transformer T7) Failure
        elif component_id == "T7":
            # T7 fails -> E-S1-T7 & E-T7-F3 failed
            # F3 loses source, F3 & L1 disconnected
            # H1 (2.5 MW) transfers to F5. F5 load becomes 4.0 + 2.5 = 6.5 MW (108.3% of 6.0 MW -> overloaded)
            # T8 load becomes 7.5 + 2.5 = 10.0 MW (100% of 10.0 MW -> warning)
            self._node_data["T7"]["load_mw"] = 0.0
            
            self._node_data["F3"]["status"] = "disconnected"
            self._node_data["F3"]["load_mw"] = 0.0
            disconnected_nodes.append("F3")
            
            self._node_data["L1"]["status"] = "disconnected"
            self._node_data["L1"]["load_mw"] = 0.0
            disconnected_nodes.append("L1")
            
            self._node_data["F5"]["status"] = "overloaded"
            self._node_data["F5"]["load_mw"] = 6.5
            overloaded_nodes.append("F5")
            
            self._node_data["T8"]["status"] = "warning"
            self._node_data["T8"]["load_mw"] = 10.0
            warning_nodes.append("T8")
            
            self._node_data["H1"]["status"] = "at_risk"
            self._node_data["H1"]["load_mw"] = 2.5
            warning_nodes.append("H1")
            
            # Edges
            self._edge_data["E-S1-T7"]["status"] = "failed"
            self._edge_data["E-S1-T7"]["load_mw"] = 0.0
            affected_edges.append("E-S1-T7")
            
            self._edge_data["E-T7-F3"]["status"] = "failed"
            self._edge_data["E-T7-F3"]["load_mw"] = 0.0
            affected_edges.append("E-T7-F3")
            
            self._edge_data["E-F3-L1"]["status"] = "disconnected"
            self._edge_data["E-F3-L1"]["load_mw"] = 0.0
            affected_edges.append("E-F3-L1")
            
            self._edge_data["E-F3-H1"]["status"] = "disconnected"
            self._edge_data["E-F3-H1"]["load_mw"] = 0.0
            affected_edges.append("E-F3-H1")
            
            self._edge_data["E-S1-T8"]["status"] = "warning"
            self._edge_data["E-S1-T8"]["load_mw"] = 10.0
            affected_edges.append("E-S1-T8")
            
            self._edge_data["E-T8-F5"]["status"] = "warning"
            self._edge_data["E-T8-F5"]["load_mw"] = 8.0
            affected_edges.append("E-T8-F5")
            
            self._edge_data["E-F5-H1"]["status"] = "rerouted"
            self._edge_data["E-F5-H1"]["load_mw"] = 2.5
            affected_edges.append("E-F5-H1")
            
        # F3 (Feeder F3) Failure
        elif component_id == "F3":
            # F3 fails -> E-T7-F3, E-F3-L1, E-F3-H1 failed
            # T7 drops to 0.0 load (or idle)
            # L1 disconnected
            # H1 (2.5 MW) transfers to F5. F5 load becomes 4.0 + 2.5 = 6.5 MW (overloaded), T8 becomes 10.0 MW (warning)
            # H1 is at_risk
            self._node_data["F3"]["load_mw"] = 0.0
            self._node_data["T7"]["load_mw"] = 0.0
            
            self._node_data["L1"]["status"] = "disconnected"
            self._node_data["L1"]["load_mw"] = 0.0
            disconnected_nodes.append("L1")
            
            self._node_data["F5"]["status"] = "overloaded"
            self._node_data["F5"]["load_mw"] = 6.5
            overloaded_nodes.append("F5")
            
            self._node_data["T8"]["status"] = "warning"
            self._node_data["T8"]["load_mw"] = 10.0
            warning_nodes.append("T8")
            
            self._node_data["H1"]["status"] = "at_risk"
            self._node_data["H1"]["load_mw"] = 2.5
            warning_nodes.append("H1")
            
            # Edges
            self._edge_data["E-T7-F3"]["status"] = "failed"
            self._edge_data["E-T7-F3"]["load_mw"] = 0.0
            affected_edges.append("E-T7-F3")
            
            self._edge_data["E-F3-L1"]["status"] = "failed"
            self._edge_data["E-F3-L1"]["load_mw"] = 0.0
            affected_edges.append("E-F3-L1")
            
            self._edge_data["E-F3-H1"]["status"] = "failed"
            self._edge_data["E-F3-H1"]["load_mw"] = 0.0
            affected_edges.append("E-F3-H1")
            
            self._edge_data["E-S1-T7"]["status"] = "normal"
            self._edge_data["E-S1-T7"]["load_mw"] = 0.0
            
            self._edge_data["E-S1-T8"]["status"] = "warning"
            self._edge_data["E-S1-T8"]["load_mw"] = 10.0
            affected_edges.append("E-S1-T8")
            
            self._edge_data["E-T8-F5"]["status"] = "warning"
            self._edge_data["E-T8-F5"]["load_mw"] = 8.0
            affected_edges.append("E-T8-F5")
            
            self._edge_data["E-F5-H1"]["status"] = "rerouted"
            self._edge_data["E-F5-H1"]["load_mw"] = 2.5
            affected_edges.append("E-F5-H1")
            
        # T8 (Transformer T8) Failure
        elif component_id == "T8":
            # T8 fails -> E-S1-T8, E-T8-F5 failed
            # F5 & L2 disconnected
            # H1 remains safely supplied via primary feeder F3
            self._node_data["T8"]["load_mw"] = 0.0
            
            self._node_data["F5"]["status"] = "disconnected"
            self._node_data["F5"]["load_mw"] = 0.0
            disconnected_nodes.append("F5")
            
            self._node_data["L2"]["status"] = "disconnected"
            self._node_data["L2"]["load_mw"] = 0.0
            disconnected_nodes.append("L2")
            
            # H1 remains safe on F3
            self._node_data["H1"]["status"] = "normal"
            
            # Edges
            self._edge_data["E-S1-T8"]["status"] = "failed"
            self._edge_data["E-S1-T8"]["load_mw"] = 0.0
            affected_edges.append("E-S1-T8")
            
            self._edge_data["E-T8-F5"]["status"] = "failed"
            self._edge_data["E-T8-F5"]["load_mw"] = 0.0
            affected_edges.append("E-T8-F5")
            
            self._edge_data["E-F5-L2"]["status"] = "disconnected"
            self._edge_data["E-F5-L2"]["load_mw"] = 0.0
            affected_edges.append("E-F5-L2")
            
            self._edge_data["E-F5-H1"]["status"] = "disconnected"
            self._edge_data["E-F5-H1"]["load_mw"] = 0.0
            affected_edges.append("E-F5-H1")
            
        # F5 (Feeder F5) Failure
        elif component_id == "F5":
            # F5 fails -> E-T8-F5, E-F5-L2, E-F5-H1 failed
            # T8 load drops
            # L2 disconnected
            # H1 safe on primary feeder F3
            self._node_data["F5"]["load_mw"] = 0.0
            self._node_data["T8"]["load_mw"] = 0.0
            
            self._node_data["L2"]["status"] = "disconnected"
            self._node_data["L2"]["load_mw"] = 0.0
            disconnected_nodes.append("L2")
            
            # H1 safe on F3
            self._node_data["H1"]["status"] = "normal"
            
            # Edges
            self._edge_data["E-T8-F5"]["status"] = "failed"
            self._edge_data["E-T8-F5"]["load_mw"] = 0.0
            affected_edges.append("E-T8-F5")
            
            self._edge_data["E-F5-L2"]["status"] = "failed"
            self._edge_data["E-F5-L2"]["load_mw"] = 0.0
            affected_edges.append("E-F5-L2")
            
            self._edge_data["E-F5-H1"]["status"] = "failed"
            self._edge_data["E-F5-H1"]["load_mw"] = 0.0
            affected_edges.append("E-F5-H1")
            
        # H1 (Hospital) Failure
        elif component_id == "H1":
            self._node_data["H1"]["status"] = "failed"
            self._node_data["H1"]["load_mw"] = 0.0
            self._edge_data["E-F3-H1"]["status"] = "failed"
            self._edge_data["E-F3-H1"]["load_mw"] = 0.0
            affected_edges.append("E-F3-H1")
            self._edge_data["E-F5-H1"]["status"] = "disconnected"
            affected_edges.append("E-F5-H1")
            
        # L1 Failure
        elif component_id == "L1":
            self._node_data["L1"]["status"] = "failed"
            self._node_data["L1"]["load_mw"] = 0.0
            self._edge_data["E-F3-L1"]["status"] = "failed"
            self._edge_data["E-F3-L1"]["load_mw"] = 0.0
            affected_edges.append("E-F3-L1")
            self._node_data["F3"]["load_mw"] = max(0.0, self._node_data["F3"]["load_mw"] - 2.0)
            
        # L2 Failure
        elif component_id == "L2":
            self._node_data["L2"]["status"] = "failed"
            self._node_data["L2"]["load_mw"] = 0.0
            self._edge_data["E-F5-L2"]["status"] = "failed"
            self._edge_data["E-F5-L2"]["load_mw"] = 0.0
            affected_edges.append("E-F5-L2")
            self._node_data["F5"]["load_mw"] = max(0.0, self._node_data["F5"]["load_mw"] - 2.0)
            
        # Fallback generic handling
        else:
            disc = self.identify_disconnected_nodes()
            for n_list in disc.values():
                for n_id in n_list:
                    if n_id != component_id:
                        self._node_data[n_id]["status"] = "disconnected"
                        disconnected_nodes.append(n_id)

        # Sync graph nodes
        for n_id, data in self._node_data.items():
            if self.graph.has_node(n_id):
                self.graph.nodes[n_id].update(data)
                
        # Sync graph edges
        for e_id, data in self._edge_data.items():
            src = data["source"]
            tgt = data["target"]
            if self.graph.has_edge(src, tgt):
                self.graph.edges[src, tgt].update(data)

        return {
            "warning": warning_nodes,
            "overloaded": overloaded_nodes,
            "disconnected": disconnected_nodes,
            "affected_edges": affected_edges
        }
