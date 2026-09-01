"""
GridTwin common data models and schemas.

Defines normalized component contract for use across the system.
Adapters translate between GridTwin schema and restoration module schemas.
"""

from typing import List, Literal, Optional
from pydantic import BaseModel, Field


# Node/Component Status
StatusType = Literal[
    "normal",
    "warning",
    "high_risk",
    "critical",
    "failed",
    "isolated",
    "disconnected"
]

# Component Types
ComponentType = Literal[
    "source",
    "substation",
    "transformer",
    "feeder",
    "bus",
    "load",
    "hospital",
    "emergency_service"
]


class NodeSchema(BaseModel):
    """Represents a grid component (node)."""
    id: str = Field(..., description="Unique component identifier")
    name: str = Field(..., description="Human-readable component name")
    type: ComponentType = Field(..., description="Component type")
    capacity_mw: float = Field(..., description="Maximum capacity in MW")
    load_mw: float = Field(..., description="Current load in MW")
    status: StatusType = Field(default="normal", description="Component status")
    criticality: float = Field(
        default=0.0,
        description="Criticality score 0-1"
    )
    is_critical_load: bool = Field(
        default=False,
        description="Is this a critical facility (hospital, emergency service)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": "T7",
                "name": "Transformer T7",
                "type": "transformer",
                "capacity_mw": 10.0,
                "load_mw": 8.0,
                "status": "normal",
                "criticality": 0.82,
                "is_critical_load": False
            }
        }


class EdgeSchema(BaseModel):
    """Represents a connection between components (edge)."""
    id: str = Field(..., description="Unique edge identifier")
    source: str = Field(..., description="Source node ID")
    target: str = Field(..., description="Target node ID")
    capacity_mw: float = Field(..., description="Maximum capacity in MW")
    load_mw: float = Field(..., description="Current load in MW")
    status: StatusType = Field(default="normal", description="Edge status")

    class Config:
        json_schema_extra = {
            "example": {
                "id": "E1",
                "source": "T7",
                "target": "F3",
                "capacity_mw": 8.0,
                "load_mw": 6.0,
                "status": "normal"
            }
        }


class GridSummary(BaseModel):
    """Summary statistics of grid state."""
    total: int = Field(..., description="Total components")
    healthy: int = Field(..., description="Healthy components")
    at_risk: int = Field(..., description="At-risk components")
    failed: int = Field(..., description="Failed components")
    total_load_mw: float = Field(..., description="Total load in MW")
    critical_loads_at_risk: int = Field(..., description="Critical loads at risk")


class GridResponse(BaseModel):
    """Complete grid state for API responses."""
    nodes: List[NodeSchema] = Field(..., description="All grid nodes")
    edges: List[EdgeSchema] = Field(..., description="All grid edges")
    summary: GridSummary = Field(..., description="Grid summary statistics")


class CascadeEvent(BaseModel):
    """Represents a single cascade event."""
    step: int = Field(..., description="Event sequence number")
    component: str = Field(..., description="Affected component ID")
    event: str = Field(
        ...,
        description="Event type: FAILED, OVERLOADED, SUPPLY_AT_RISK, DISCONNECTED"
    )
    reason: Optional[str] = Field(None, description="Reason for event")


class RiskScore(BaseModel):
    """Risk assessment for a component."""
    component_id: str = Field(..., description="Component ID")
    risk_score: float = Field(
        ...,
        description="Risk score 0-100"
    )
    risk_level: Literal["normal", "warning", "high_risk", "critical"] = Field(
        ...,
        description="Risk classification"
    )
    reason: str = Field(..., description="Explanation of risk")


class RiskAnalysis(BaseModel):
    """Risk analysis results."""
    risks: List[RiskScore] = Field(..., description="Risk scores for components")
    next_likely_component: Optional[str] = Field(
        None,
        description="Component most likely to fail next"
    )
    overall_risk: float = Field(..., description="Overall system risk 0-100")


class RestorationAction(BaseModel):
    """Single restoration action."""
    order: int = Field(..., description="Action sequence number")
    action: str = Field(
        ...,
        description="Action type: isolate, reroute, restore"
    )
    component: Optional[str] = Field(None, description="Primary component")
    from_component: Optional[str] = Field(None, description="Source for reroute")
    via_component: Optional[str] = Field(None, description="Via component for reroute")


class RestorationStrategy(BaseModel):
    """Restoration strategy recommendation."""
    strategy_id: str = Field(..., description="Strategy identifier")
    score: float = Field(..., description="Strategy score 0-100")
    actions: List[RestorationAction] = Field(..., description="Ordered actions")


class RestorationComparison(BaseModel):
    """Comparison metrics before/after restoration."""
    before_optimization: dict = Field(..., description="Pre-restoration metrics")
    after_optimization: dict = Field(..., description="Post-restoration metrics")
    disruption_reduction_percent: float = Field(
        ...,
        description="Percentage of disruption reduced"
    )


class RestorationResult(BaseModel):
    """Complete restoration optimization result."""
    recommended_strategy: Optional[RestorationStrategy] = Field(
        None,
        description="Recommended restoration strategy"
    )
    comparison: Optional[RestorationComparison] = Field(
        None,
        description="Before/after comparison"
    )
    available: bool = Field(
        default=False,
        description="Is optimizer available"
    )
    reason: Optional[str] = Field(None, description="Explanation if unavailable")


class SimulationMetrics(BaseModel):
    """Metrics for a simulation scenario."""
    components_affected: int = Field(..., description="Number of affected components")
    critical_services_at_risk: int = Field(..., description="Critical services at risk")
    estimated_consumers_affected: int = Field(
        ...,
        description="Estimated number of consumers"
    )


class SimulationResponse(BaseModel):
    """Complete simulation response."""
    scenario_id: str = Field(..., description="Unique scenario identifier")
    
    failed_component: Optional[NodeSchema] = Field(
        None,
        description="The initially failed component"
    )
    
    affected_components: List[NodeSchema] = Field(
        ...,
        description="All affected components"
    )
    
    critical_loads_at_risk: List[NodeSchema] = Field(
        ...,
        description="Critical facilities at risk"
    )
    
    cascade: List[CascadeEvent] = Field(
        ...,
        description="Cascade event sequence"
    )
    
    risk_summary: RiskAnalysis = Field(
        ...,
        description="Risk analysis results"
    )
    
    risk_scores: List[RiskScore] = Field(
        ...,
        description="Detailed risk scores"
    )
    
    restoration: RestorationResult = Field(
        ...,
        description="Restoration optimization results"
    )
    
    metrics: SimulationMetrics = Field(
        ...,
        description="Impact metrics"
    )


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = Field(..., description="System status")
    simulation_engine: str = Field(..., description="Simulation engine status")
    risk_engine: str = Field(..., description="Risk engine status")
    optimizer: str = Field(..., description="Optimizer status")


class SystemResponse(BaseModel):
    """System info response."""
    system: str = Field(..., description="System name")
    status: str = Field(..., description="System status")
