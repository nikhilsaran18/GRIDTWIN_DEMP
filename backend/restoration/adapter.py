"""
Input adapters for GridTwin Restoration Module.

Boundary Isolation Architecture:
--------------------------------
Nikhil's Future Grid/Cascade Data
                ↓
      NikhilGridAdapter (or MockGridAdapter)
                ↓
    Internal Restoration Model (GridComponent, GridConnection, LoadDemand)
                ↓
    Restoration Optimizer Engine
                ↓
      Structured Result

When Nikhil provides his grid dataset and cascade output schema, only NikhilGridAdapter
needs to be implemented. The core restoration optimization algorithms remain untouched.
"""

from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, Optional
from restoration.models import GridComponent, GridConnection, LoadDemand
from mock_data.mock_grid import get_benchmark_grid, get_bottleneck_grid, get_islanded_no_path_grid


class BaseGridAdapter(ABC):
    """Abstract interface defining the input data contract for the restoration engine."""

    @abstractmethod
    def load_grid_state(self) -> Tuple[List[GridComponent], List[GridConnection], List[LoadDemand]]:
        """
        Loads and returns the internal representation of components, connections, and loads.
        """
        pass

    @abstractmethod
    def extract_failure_state(self, raw_input: Any) -> List[str]:
        """
        Extracts the list of failed component IDs from an upstream simulation payload.
        """
        pass


class MockGridAdapter(BaseGridAdapter):
    """Adapter for synthetic mock test scenarios."""

    def __init__(self, scenario: str = "benchmark"):
        self.scenario = scenario

    def load_grid_state(self) -> Tuple[List[GridComponent], List[GridConnection], List[LoadDemand]]:
        if self.scenario == "bottleneck":
            return get_bottleneck_grid()
        elif self.scenario == "no_path":
            return get_islanded_no_path_grid()
        return get_benchmark_grid()

    def extract_failure_state(self, raw_input: Any) -> List[str]:
        if isinstance(raw_input, dict):
            return raw_input.get("failed_components", [])
        elif isinstance(raw_input, list):
            return raw_input
        return []


class NikhilGridAdapter(BaseGridAdapter):
    """
    Adapter placeholder for Member 1 (Nikhil)'s upstream grid & cascade simulation engine.

    Integration Guide for Nikhil's Schema:
    --------------------------------------
    When Nikhil provides his grid JSON / dict format, map his fields into the internal
    Pydantic models below:
    - nikhil_node -> GridComponent(id, name, type, capacity_mw, base_load_mw, status)
    - nikhil_branch/line -> GridConnection(id, source_id, target_id, capacity_mw, base_load_mw, status)
    - nikhil_load -> LoadDemand(id, node_id, demand_mw, load_type, priority, is_critical)
    """

    def __init__(self, nikhil_payload: Optional[Dict[str, Any]] = None):
        self.raw_data = nikhil_payload or {}

    def load_grid_state(self) -> Tuple[List[GridComponent], List[GridConnection], List[LoadDemand]]:
        if not self.raw_data:
            # Fallback to benchmark until Nikhil payload is injected
            return get_benchmark_grid()

        components: List[GridComponent] = []
        connections: List[GridConnection] = []
        loads: List[LoadDemand] = []

        # Example Mapping Hook:
        # for item in self.raw_data.get("substations", []): ...
        # for branch in self.raw_data.get("lines", []): ...
        # for load in self.raw_data.get("consumers", []): ...

        return components, connections, loads

    def extract_failure_state(self, raw_input: Any) -> List[str]:
        if isinstance(raw_input, dict):
            return raw_input.get("failed_elements", raw_input.get("failed_components", []))
        elif isinstance(raw_input, list):
            return raw_input
        return []
