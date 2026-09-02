"""
GridTwin Backend - Main FastAPI Application

Complete backend system for grid simulation, cascade analysis, risk assessment,
and restoration optimization.

Architecture:
                 FRONTEND (separate)
                        │
                        ▼
                  FastAPI (main.py)
                        │
              ┌─────────┼─────────┐
              ▼         ▼         ▼
        GridDigitalTwin CascadeEngine RiskService OptimizerAdapter
              │         │         │         │
              └─────────┴─────────┴─────────┘
                        ▼
         EXISTING RestorationService ✓ (preserved)
         EXISTING Optimizer ✓ (preserved)
"""

import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel

from models.grid_schemas import (
    GridResponse,
    HealthResponse,
    SystemResponse,
    SimulationResponse,
    SimulationMetrics,
    CascadeEvent,
    RiskAnalysis,
)
from core.grid_engine import GridDigitalTwin
from core.cascade_engine import CascadeEngine
from services.risk_service import RiskService
from services.optimizer_adapter import OptimizerAdapter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ============================================================================
# FastAPI Application Setup
# ============================================================================

app = FastAPI(
    title="GridTwin",
    description="AI-Assisted Grid Restoration and Cascade Analysis Engine",
    version="1.0.0"
)

# Repository root containing index.html, style.css, and script.js
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# CORS Configuration for frontend development
ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================================
# Global State - Shared Services
# ============================================================================

# Initialize core engines
def _init_grid() -> GridDigitalTwin:
    """Initialize GridDigitalTwin with dataset."""
    dataset_path = Path(__file__).parent / "data" / "grid.json"
    try:
        return GridDigitalTwin(dataset_path=str(dataset_path))
    except Exception as e:
        logger.error(f"Failed to initialize grid: {e}")
        raise


# Global instances - created once on startup
grid_instance: Optional[GridDigitalTwin] = None
cascade_engine: Optional[CascadeEngine] = None
risk_service: Optional[RiskService] = None
optimizer_adapter: Optional[OptimizerAdapter] = None

# Track simulation scenarios
scenarios = {}  # scenario_id -> scenario data


def get_grid() -> GridDigitalTwin:
    """Get or create grid instance."""
    global grid_instance
    if grid_instance is None:
        grid_instance = _init_grid()
    return grid_instance


def get_cascade_engine() -> CascadeEngine:
    """Get or create cascade engine."""
    global cascade_engine
    if cascade_engine is None:
        grid = get_grid()
        cascade_engine = CascadeEngine(grid)
    return cascade_engine


def get_risk_service() -> RiskService:
    """Get or create risk service."""
    global risk_service
    if risk_service is None:
        grid = get_grid()
        risk_service = RiskService(grid)
    return risk_service


def get_optimizer() -> OptimizerAdapter:
    """Get or create optimizer adapter."""
    global optimizer_adapter
    if optimizer_adapter is None:
        grid = get_grid()
        optimizer_adapter = OptimizerAdapter(grid)
    return optimizer_adapter


# ============================================================================
# Request/Response Models
# ============================================================================

class FailureSimulationRequest(BaseModel):
    """Request to simulate component failure."""
    component_id: str


class ResetRequest(BaseModel):
    """Request to reset simulation."""
    pass


# ============================================================================
# Root Endpoints
# ============================================================================

@app.get("/", response_model=SystemResponse)
async def root():
    """System status endpoint."""
    return SystemResponse(
        system="GridTwin",
        status="online"
    )


@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    """Serve the GridTwin frontend."""
    return FileResponse(PROJECT_ROOT / "index.html")


@app.get("/style.css", include_in_schema=False)
async def frontend_css():
    """Serve the frontend stylesheet."""
    return FileResponse(PROJECT_ROOT / "style.css", media_type="text/css")


@app.get("/script.js", include_in_schema=False)
async def frontend_js():
    """Serve the frontend JavaScript."""
    return FileResponse(
        PROJECT_ROOT / "script.js",
        media_type="application/javascript",
    )


@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    grid = get_grid()
    cascade = get_cascade_engine()
    risk = get_risk_service()
    optimizer = get_optimizer()
    
    return HealthResponse(
        status="healthy",
        simulation_engine="online" if grid else "offline",
        risk_engine="online" if risk else "offline",
        optimizer="online" if optimizer.is_available() else "offline"
    )


# ============================================================================
# Grid Information Endpoints
# ============================================================================

@app.get("/api/grid", response_model=GridResponse)
async def get_grid_state():
    """
    Get current grid state.
    
    Returns all nodes, edges, and summary statistics.
    """
    try:
        grid = get_grid()
        return grid.serialize()
    except Exception as e:
        logger.error(f"Error getting grid state: {e}")
        raise HTTPException(status_code=500, detail="Failed to get grid state")


@app.get("/api/components/{component_id}")
async def get_component(component_id: str):
    """
    Get information about a specific component.
    
    Args:
        component_id: Component ID
        
    Returns:
        Component data
    """
    try:
        grid = get_grid()
        component = grid.get_component(component_id)
        if not component:
            raise HTTPException(
                status_code=404,
                detail=f"Component {component_id} not found"
            )
        return component
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting component: {e}")
        raise HTTPException(status_code=500, detail="Failed to get component")


# ============================================================================
# Simulation Endpoints
# ============================================================================

@app.post("/api/simulate/failure", response_model=SimulationResponse)
async def simulate_failure(request: FailureSimulationRequest):
    """
    Simulate a component failure and analyze cascade/impact.
    
    This is the PRIMARY simulation endpoint. It:
    1. Validates the component exists
    2. Runs cascade analysis
    3. Performs risk assessment
    4. Invokes optimizer for restoration
    5. Compiles comprehensive impact report
    
    Args:
        request: FailureSimulationRequest with component_id
        
    Returns:
        Complete simulation response with cascade, risk, and restoration
    """
    try:
        component_id = request.component_id
        grid = get_grid()
        cascade_eng = get_cascade_engine()
        risk_svc = get_risk_service()
        optimizer = get_optimizer()
        
        # Validate component exists
        component = grid.get_component(component_id)
        if not component:
            raise HTTPException(
                status_code=404,
                detail=f"Component {component_id} not found"
            )
        
        # Create scenario ID
        scenario_id = f"SCN-{uuid.uuid4().hex[:8].upper()}"
        
        # Simulate the failure on the grid
        grid.fail_component(component_id)
        
        # Run cascade analysis
        cascade_events: list[CascadeEvent] = cascade_eng.analyze_cascade(component_id)
        
        # Get affected components
        affected_components = grid.get_affected_components(component_id)
        affected_nodes = [
            grid.get_component(comp_id)
            for comp_id in affected_components
            if grid.get_component(comp_id)
        ]
        
        # Identify critical facilities at risk
        critical_facilities = grid.identify_critical_facilities()
        critical_at_risk = [
            grid.get_component(cf_id)
            for cf_id in critical_facilities
            if cf_id in affected_components and grid.get_component(cf_id)
        ]
        
        # Perform risk analysis
        risk_analysis: RiskAnalysis = risk_svc.analyze_risks()
        
        # Run restoration optimizer
        restoration_result = optimizer.optimize_restoration(component_id)
        
        # Compile metrics
        metrics = SimulationMetrics(
            components_affected=len(affected_components),
            critical_services_at_risk=len(critical_at_risk),
            estimated_consumers_affected=int(
                sum(c.get("load_mw", 0) * 1000 for c in affected_nodes)
                if affected_nodes else 0
            )
        )
        
        # Build response
        response = SimulationResponse(
            scenario_id=scenario_id,
            failed_component=component,
            affected_components=affected_nodes,
            critical_loads_at_risk=critical_at_risk,
            cascade=cascade_events,
            risk_summary=risk_analysis,
            risk_scores=risk_analysis.risks,
            restoration=restoration_result,
            metrics=metrics
        )
        
        # Store scenario
        scenarios[scenario_id] = {
            "timestamp": datetime.now().isoformat(),
            "failed_component": component_id,
            "response": response
        }
        
        logger.info(f"Simulation {scenario_id} completed for {component_id}")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Simulation failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Simulation failed")


@app.post("/api/simulation/reset")
async def reset_simulation():
    """
    Reset grid to baseline state.
    
    Clears all simulation effects and returns grid to initial state.
    """
    try:
        grid = get_grid()
        grid.reset_grid()
        logger.info("Grid reset to baseline")
        return {"status": "success", "message": "Grid reset to baseline state"}
    except Exception as e:
        logger.error(f"Reset failed: {e}")
        raise HTTPException(status_code=500, detail="Reset failed")


# ============================================================================
# Startup/Shutdown
# ============================================================================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info("GridTwin startup...")
    try:
        grid = get_grid()
        logger.info(f"Grid loaded with {len(grid._node_data)} nodes")
        
        cascade = get_cascade_engine()
        logger.info("Cascade engine ready")
        
        risk = get_risk_service()
        logger.info("Risk service ready")
        
        optimizer = get_optimizer()
        logger.info(f"Optimizer ready: {optimizer.is_available()}")
        
        logger.info("GridTwin startup complete ✓")
    except Exception as e:
        logger.error(f"Startup failed: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("GridTwin shutdown")


# ============================================================================
# Error Handlers
# ============================================================================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler."""
    return {
        "detail": exc.detail,
        "status_code": exc.status_code
    }


# ============================================================================
# If run directly (for development)
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )
