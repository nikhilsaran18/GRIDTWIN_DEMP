"""
NetworkX Graph Traversal and Alternate Path Generation for GridTwin.

Responsibilities:
- Build electrical graph topology from components and connections.
- Prune failed/isolated components and inactive paths.
- Automatically identify affected/unserved loads losing power from upstream failures.
- Discover all valid, simple candidate alternate supply paths from operational substations to affected loads.
"""

from typing import List, Dict, Set, Tuple, Optional
import networkx as nx
from restoration.models import (
    GridComponent,
    GridConnection,
    LoadDemand,
    CandidateRoute,
    ComponentType,
    ComponentStatus,
    SwitchState,
)


class TopologyPathGenerator:
    """
    NetworkX graph analyzer for grid connectivity and candidate restoration route discovery.
    """

    def __init__(
        self,
        components: List[GridComponent],
        connections: List[GridConnection],
        loads: List[LoadDemand],
    ):
        self.components = {c.id: c for c in components}
        self.connections = {conn.id: conn for conn in connections}
        self.loads = {load.id: load for load in loads}
        self.load_node_map = {load.id: load.node_id for load in loads}

        # Build master graph
        self.master_graph = self._build_graph(components, connections)

    def _build_graph(
        self, components: List[GridComponent], connections: List[GridConnection]
    ) -> nx.Graph:
        """Constructs an undirected NetworkX graph representing the grid topology."""
        g = nx.Graph()
        for c in components:
            g.add_node(
                c.id,
                name=c.name,
                type=c.type.value if hasattr(c.type, "value") else str(c.type),
                capacity_mw=c.capacity_mw,
                base_load_mw=c.base_load_mw,
                status=c.status.value if hasattr(c.status, "value") else str(c.status),
            )

        for conn in connections:
            g.add_edge(
                conn.source_id,
                conn.target_id,
                id=conn.id,
                capacity_mw=conn.capacity_mw,
                base_load_mw=conn.base_load_mw,
                status=conn.status.value if hasattr(conn.status, "value") else str(conn.status),
                is_switchable=conn.is_switchable,
                switch_state=conn.switch_state.value if hasattr(conn.switch_state, "value") else str(conn.switch_state),
            )
        return g

    def get_operational_substations(self, failed_components: Set[str]) -> List[str]:
        """Returns all substation IDs that are not marked as failed."""
        substations = []
        for c_id, comp in self.components.items():
            if comp.type == ComponentType.SUBSTATION and c_id not in failed_components:
                if comp.status != ComponentStatus.FAILED:
                    substations.append(c_id)
        return substations

    def get_pruned_graph(self, failed_components: Set[str]) -> nx.Graph:
        """
        Returns a copy of the graph with all failed components and connections removed.
        NetworkX remove_node automatically removes all incident edges.
        """
        pruned_g = self.master_graph.copy()
        failed_set = set(failed_components)

        # 1. Remove explicitly failed component nodes and status==FAILED nodes
        for node in list(pruned_g.nodes):
            comp = self.components.get(node)
            if node in failed_set or (comp and comp.status == ComponentStatus.FAILED):
                pruned_g.remove_node(node)

        # 2. Remove explicitly failed connections and status==FAILED connections
        for u, v, data in list(pruned_g.edges(data=True)):
            conn_id = data.get("id")
            conn = self.connections.get(conn_id)
            if conn_id in failed_set or (conn and conn.status == ComponentStatus.FAILED):
                pruned_g.remove_edge(u, v)

        return pruned_g

    def identify_affected_loads(self, failed_components: List[str]) -> Tuple[List[LoadDemand], List[LoadDemand]]:
        """
        Identifies which loads lost power due to component failures.

        Returns:
            (affected_loads, still_served_loads)
        """
        failed_set = set(failed_components)
        # Start from pruned graph (all failed nodes/edges already removed)
        baseline_g = self.get_pruned_graph(failed_set)

        # Remove normally OPEN tie-switches because in baseline state they are not closed
        for u, v, data in list(baseline_g.edges(data=True)):
            if data.get("switch_state") == SwitchState.OPEN.value:
                baseline_g.remove_edge(u, v)

        operational_substations = self.get_operational_substations(failed_set)

        affected_loads: List[LoadDemand] = []
        still_served_loads: List[LoadDemand] = []

        for load_id, load in self.loads.items():
            node_id = load.node_id
            is_reachable = False

            if node_id in baseline_g:
                for sub in operational_substations:
                    if sub in baseline_g and nx.has_path(baseline_g, sub, node_id):
                        is_reachable = True
                        break

            if is_reachable:
                still_served_loads.append(load)
            else:
                affected_loads.append(load)

        return affected_loads, still_served_loads

    def generate_candidate_routes_for_load(
        self,
        load: LoadDemand,
        failed_components: List[str],
        max_depth: int = 15,
    ) -> List[CandidateRoute]:
        """
        Discovers all simple alternate paths from operational substations to the target load node,
        utilizing switchable tie-lines in the pruned graph.
        """
        failed_set = set(failed_components)
        pruned_g = self.get_pruned_graph(failed_set)
        operational_substations = self.get_operational_substations(failed_set)

        load_node = load.node_id
        if load_node not in pruned_g:
            return []

        candidate_routes: List[CandidateRoute] = []
        route_index = 1

        for sub in operational_substations:
            if sub not in pruned_g:
                continue

            try:
                paths = list(nx.all_simple_paths(pruned_g, source=sub, target=load_node, cutoff=max_depth))
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue

            for path in paths:
                # Verify no node in path is failed
                if any(node in failed_set for node in path):
                    continue

                feeders_used: List[str] = []
                transformers_used: List[str] = []
                edges_used: List[str] = []

                for node_id in path:
                    comp = self.components.get(node_id)
                    if comp:
                        if comp.type == ComponentType.FEEDER:
                            feeders_used.append(comp.id)
                        elif comp.type == ComponentType.TRANSFORMER:
                            transformers_used.append(comp.id)

                for i in range(len(path) - 1):
                    u, v = path[i], path[i + 1]
                    edge_data = pruned_g.get_edge_data(u, v)
                    if edge_data and "id" in edge_data:
                        edges_used.append(edge_data["id"])

                route_id = f"ROUTE_{load.id}_{route_index}"
                candidate_routes.append(
                    CandidateRoute(
                        route_id=route_id,
                        load_id=load.id,
                        source_substation_id=sub,
                        path_nodes=path,
                        path_edges=edges_used,
                        feeders_used=feeders_used,
                        transformers_used=transformers_used,
                        total_hops=len(path) - 1,
                        estimated_added_load_mw=load.demand_mw,
                    )
                )
                route_index += 1

        return candidate_routes

    def generate_all_alternate_routes(
        self,
        affected_loads: List[LoadDemand],
        failed_components: List[str],
    ) -> Dict[str, List[CandidateRoute]]:
        """
        Generates candidate alternate routes for all affected loads.
        Returns: Dict[load_id, List[CandidateRoute]]
        """
        routes_by_load: Dict[str, List[CandidateRoute]] = {}
        for load in affected_loads:
            routes = self.generate_candidate_routes_for_load(load, failed_components)
            routes_by_load[load.id] = routes
        return routes_by_load
