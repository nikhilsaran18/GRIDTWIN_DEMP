"""
Domain-specific exceptions for GridTwin Restoration & Optimization module.
"""

class GridTwinRestorationError(Exception):
    """Base exception for all restoration module errors."""
    pass


class InfeasibleRestorationError(GridTwinRestorationError):
    """Raised when no feasible restoration plan satisfies capacity and connectivity constraints."""
    def __init__(self, message: str, diagnostics: dict = None):
        super().__init__(message)
        self.diagnostics = diagnostics or {}


class ComponentNotFoundError(GridTwinRestorationError):
    """Raised when a referenced grid component is not found in the topology."""
    pass


class InvalidGridTopologyError(GridTwinRestorationError):
    """Raised when the grid topology is malformed or disjoint."""
    pass


class CapacityViolationError(GridTwinRestorationError):
    """Raised when a candidate route exceeds rated component capacity."""
    def __init__(self, component_id: str, new_load: float, capacity: float, component_type: str = "component"):
        message = (
            f"Capacity violation on {component_type} '{component_id}': "
            f"new load {new_load:.2f} MW exceeds rated capacity {capacity:.2f} MW "
            f"({(new_load / capacity * 100):.1f}% utilization)"
        )
        super().__init__(message)
        self.component_id = component_id
        self.new_load = new_load
        self.capacity = capacity
        self.component_type = component_type
