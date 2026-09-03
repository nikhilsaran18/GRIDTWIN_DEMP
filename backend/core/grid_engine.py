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
    - Load calculation
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
            # Source doesn't exist or is isolated
            if source in self.graph:
                reachable = {source}
        
        return reachable
    
    def identify_disconnected_nodes(self) -> Dict[str, List[str]]:
        """
        Identify nodes disconnected from sources.
        
        Returns:
            Dict mapping node type to list of disconnected node IDs
        """
        # Find all source nodes
        sources = [
            node_id for node_id, data in self._node_data.items()
            if data.get("type") == "source"
        ]
        
        # Find all reachable nodes
        reachable = set()
        for source in sources:
            reachable.update(self.calculate_connectivity(source))
        
        # Identify disconnected
        all_nodes = set(self._node_data.keys())
        disconnected = all_nodes - reachable
        
        # Categorize by type
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
        return min(percentage, 100.0)
    
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
            if data.get("status") in ["warning", "high_risk", "critical"]
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
        
        Currently returns all components no longer reachable from any source.
        
        Args:
            component_id: ID of failed component
            
        Returns:
            List of affected component IDs (not including the failed one)
        """
        # Store original status
        original_status = self.get_component_status(component_id)
        
        # Mark as failed
        self.set_component_status(component_id, "failed")
        
        # Find disconnected
        disconnected_dict = self.identify_disconnected_nodes()
        disconnected = []
        for node_list in disconnected_dict.values():
            disconnected.extend(node_list)
        
        # Restore original status
        if original_status:
            self.set_component_status(component_id, original_status)
        
        # Remove the originally-failed component from results
        affected = [n for n in disconnected if n != component_id]
        return affected

    def apply_failure_scenario(self, component_id: str) -> Dict[str, List[str]]:
        """Apply one failure and classify current node and edge connectivity."""
        if component_id not in self._node_data:
            return {"warning": [], "overloaded": [], "disconnected": [], "affected_edges": []}

        self.fail_component(component_id)
        disconnected = set()
        for node_ids in self.identify_disconnected_nodes().values():
            disconnected.update(node_ids)

        for node_id, node_data in self._node_data.items():
            if node_id == component_id:
                status = "failed"
            elif node_id in disconnected:
                status = "critical_risk" if node_data.get("is_critical_load") else "disconnected"
            else:
                status = "normal"
            node_data["status"] = status
            self.graph.nodes[node_id]["status"] = status

        affected_edges = []
        for edge_id, edge_data in self._edge_data.items():
            source = edge_data["source"]
            target = edge_data["target"]
            if source == component_id or target == component_id:
                status = "failed"
            elif source in disconnected or target in disconnected:
                status = "disconnected"
            else:
                status = "normal"
            edge_data["status"] = status
            self.graph.edges[source, target]["status"] = status
            if status != "normal":
                affected_edges.append(edge_id)

        return {
            "warning": [],
            "overloaded": [],
            "disconnected": sorted(disconnected),
            "affected_edges": affected_edges,
        }
