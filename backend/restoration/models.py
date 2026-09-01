"""
Data models and schemas for GridTwin Restoration & Optimization module.

Semantic Convention for Load & Capacity:
----------------------------------------
1. base_load_mw (or current_load_mw):
   Represents the active baseline power currently flowing through an operational component
   from other uninterrupted, ongoing loads at the time of failure.
2. demand_mw:
   The power demand required by a specific load node.
3. interrupted_demand_mw:
   The demand of loads whose supply was disconnected by failed components.
4. restored_demand_mw:
   The demand of interrupted loads that are successfully re-energized via a valid alternate route.
5. post_restoration_load_mw:
   Calculated as: base_load_mw + sum(demand_mw of newly restored loads traversing this component).
   * Note: Disconnected/affected loads are NOT counted in base_load_mw, preventing double-counting.
"""

from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field


class ComponentType(str, Enum):
    SUBSTATION = "substation"
    TRANSFORMER = "transformer"
    FEEDER = "feeder"
    BUS = "bus"
    LOAD = "load"
    CRITICAL_FACILITY = "critical_facility"


class ComponentStatus(str, Enum):
    OPERATIONAL = "OPERATIONAL"
    FAILED = "FAILED"
    DEGRADED = "DEGRADED"
    ISOLATED = "ISOLATED"


class SwitchState(str, Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"


class LoadType(str, Enum):
    HOSPITAL = "hospital"
    EMERGENCY = "emergency"
    CRITICAL_INFRASTRUCTURE = "critical_infrastructure"
    COMMERCIAL = "commercial"
    RESIDENTIAL = "residential"


class ActionType(str, Enum):
    ISOLATE = "ISOLATE"
    REROUTE = "REROUTE"
    RESTORE = "RESTORE"


class RestorationStatus(str, Enum):
    OPTIMAL = "OPTIMAL"
    FEASIBLE = "FEASIBLE"
    INFEASIBLE = "INFEASIBLE"
    NO_FEASIBLE_RESTORATION = "NO_FEASIBLE_RESTORATION"


class GridComponent(BaseModel):
    id: str
    name: str
    type: ComponentType
    capacity_mw: float = Field(..., description="Maximum rated thermal capacity in MW")
    base_load_mw: float = Field(0.0, description="Active uninterrupted power flow at failure instant in MW")
    status: ComponentStatus = ComponentStatus.OPERATIONAL
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def current_load_mw(self) -> float:
        """Alias for base_load_mw to maintain compatibility."""
        return self.base_load_mw


class GridConnection(BaseModel):
    id: str
    source_id: str
    target_id: str
    capacity_mw: float = Field(..., description="Line/Connection thermal capacity in MW")
    base_load_mw: float = Field(0.0, description="Active baseline flow through line in MW")
    status: ComponentStatus = ComponentStatus.OPERATIONAL
    is_switchable: bool = True
    switch_state: SwitchState = SwitchState.CLOSED
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @property
    def current_load_mw(self) -> float:
        return self.base_load_mw


class LoadDemand(BaseModel):
    id: str
    node_id: str
    name: str
    demand_mw: float = Field(..., description="Power required by the facility in MW")
    load_type: LoadType = LoadType.RESIDENTIAL
    priority: int = Field(default=10, ge=1, le=100, description="1 (lowest) to 100 (highest/hospital)")
    is_critical: bool = False
    is_served: bool = True
    pre_fault_path: List[str] = Field(default_factory=list, description="Original supply path IDs")
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CandidateRoute(BaseModel):
    route_id: str
    load_id: str
    source_substation_id: str
    path_nodes: List[str] = Field(..., description="Ordered list of node IDs from supply to load")
    path_edges: List[str] = Field(default_factory=list, description="Ordered list of edge/connection IDs")
    feeders_used: List[str] = Field(default_factory=list)
    transformers_used: List[str] = Field(default_factory=list)
    total_hops: int = 0
    estimated_added_load_mw: float = 0.0


class RestorationAction(BaseModel):
    step: int
    action: ActionType
    target: str = Field(..., description="Component or Load ID")
    load_id: Optional[str] = None
    from_path: Optional[str] = None
    to_path: Optional[str] = None
    via: List[str] = Field(default_factory=list)
    load_mw: Optional[float] = None
    details: str


class ComponentUtilization(BaseModel):
    id: str
    name: str
    type: ComponentType
    capacity_mw: float
    base_load_mw: float
    added_restoration_load_mw: float
    post_restoration_load_mw: float
    utilization_pct: float
    margin_mw: float
    margin_pct: float
    status: str = "FEASIBLE"  # FEASIBLE | OVERLOADED


class CriticalLoadsSummary(BaseModel):
    total_critical: int
    restored_critical: int
    unserved_critical: int
    restored_percentage: float
    critical_loads_details: List[Dict[str, Any]] = Field(default_factory=list)


class ImpactAnalysis(BaseModel):
    affected_loads_before: int
    affected_loads_after: int
    restored_loads_count: int
    critical_loads_affected_before: int
    critical_loads_affected_after: int
    critical_loads_restored_count: int
    interrupted_demand_before_mw: float
    interrupted_demand_after_mw: float
    restored_demand_mw: float
    disruption_reduction_pct: float
    critical_demand_restored_pct: float


class StrategyResult(BaseModel):
    strategy_id: str
    name: str
    objective_score: float
    rank: int
    restored_load_ids: List[str]
    unserved_load_ids: List[str]
    selected_routes: Dict[str, str] = Field(default_factory=dict, description="load_id -> route_id")
    critical_loads_summary: CriticalLoadsSummary
    impact: ImpactAnalysis
    max_feeder_utilization_pct: float
    max_transformer_utilization_pct: float
    recovery_sequence: List[RestorationAction]
    is_feasible: bool
    explanation: str


class RestorationResult(BaseModel):
    status: RestorationStatus
    simulation_mode: str = "SIMULATED"
    failed_components: List[str]
    affected_load_ids: List[str]
    recommended_strategy: Optional[StrategyResult] = None
    alternative_strategies: List[StrategyResult] = Field(default_factory=list)
    recovery_sequence: List[RestorationAction] = Field(default_factory=list)
    capacity_summary: Dict[str, List[ComponentUtilization]] = Field(default_factory=dict)
    impact: Optional[ImpactAnalysis] = None
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    explanation: str = ""
