"""
GridTwin Backend - Main FastAPI Application

Complete backend system for grid simulation, cascade analysis, risk assessment,
and restoration optimization.

Architecture:
                 FRONTEND (HTML5 / Three.js / Canvas)
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
         RestorationService & Optimizer ✓
"""

import sys
from pathlib import Path

# Ensure backend package directory is on sys.path for direct module imports
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import logging
import os
import uuid
from datetime import datetime
from contextlib import asynccontextmanager
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel

from models.grid_schemas import (
    GridResponse,
    HealthResponse,
    SystemResponse,
    SimulationResponse,
    SimulationMetrics,
    CascadeEvent,
    RiskAnalysis,
    NodeSchema,
    EdgeSchema,
)
from core.grid_engine import GridDigitalTwin
from core.cascade_engine import CascadeEngine
from services.risk_service import RiskService
from services.optimizer_adapter import OptimizerAdapter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Repository root containing index.html, style.css, script.js, grid3d.js
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ============================================================================
# Global State - Shared Services
# ============================================================================

def _init_grid() -> GridDigitalTwin:
    """Initialize GridDigitalTwin with dataset."""
    dataset_path = Path(__file__).parent / "data" / "grid.json"
    try:
        return GridDigitalTwin(dataset_path=str(dataset_path))
    except Exception as e:
        logger.error(f"Failed to initialize grid: {e}")
        raise


grid_instance: Optional[GridDigitalTwin] = None
cascade_engine: Optional[CascadeEngine] = None
risk_service: Optional[RiskService] = None
optimizer_adapter: Optional[OptimizerAdapter] = None

# Track simulation scenarios
scenarios: Dict[str, Any] = {}


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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan event handler for FastAPI startup and shutdown."""
    logger.info("GridTwin startup initializing engines...")
    try:
        grid = get_grid()
        logger.info(f"Grid loaded with {len(grid._node_data)} nodes")
        get_cascade_engine()
        get_risk_service()
        opt = get_optimizer()
        logger.info(f"Optimizer available: {opt.is_available()}")
        logger.info("GridTwin startup complete ✓")
    except Exception as e:
        logger.error(f"Startup initialization failed: {e}")
    yield
    logger.info("GridTwin shutdown complete")


# ============================================================================
# FastAPI Application Setup
# ============================================================================

app = FastAPI(
    title="GridTwin",
    description="AI-Assisted Grid Restoration and Cascade Analysis Engine",
    version="1.0.0",
    lifespan=lifespan
)

# CORS Configuration for frontend development
ALLOWED_ORIGINS = [
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8001",
    "http://127.0.0.1:8001",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# Request Models
# ============================================================================

class FailureSimulationRequest(BaseModel):
    """Request to simulate component failure."""
    component_id: str


class ResetRequest(BaseModel):
    """Request to reset simulation."""
    pass


# ============================================================================
# Static & Dashboard Endpoints
# ============================================================================

@app.get("/dashboard", include_in_schema=False)
async def dashboard():
    """Serve the GridTwin frontend dashboard."""
    index_file = PROJECT_ROOT / "index.html"
    if index_file.exists():
        return FileResponse(index_file)
    raise HTTPException(status_code=404, detail="index.html not found")


@app.get("/style.css", include_in_schema=False)
async def frontend_css():
    """Serve the frontend stylesheet."""
    css_file = PROJECT_ROOT / "style.css"
    if css_file.exists():
        return FileResponse(css_file, media_type="text/css")
    raise HTTPException(status_code=404, detail="style.css not found")


@app.get("/script.js", include_in_schema=False)
async def frontend_js():
    """Serve the frontend JavaScript."""
    js_file = PROJECT_ROOT / "script.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="script.js not found")


@app.get("/grid3d.js", include_in_schema=False)
async def frontend_grid3d_js():
    """Serve the 3D visualizer JavaScript."""
    grid3d_file = PROJECT_ROOT / "grid3d.js"
    if grid3d_file.exists():
        return FileResponse(grid3d_file, media_type="application/javascript")
    raise HTTPException(status_code=404, detail="grid3d.js not found")


@app.get("/favicon.ico", include_in_schema=False)
@app.get("/favicon.svg", include_in_schema=False)
async def frontend_favicon():
    """Serve the SVG favicon."""
    fav_file = PROJECT_ROOT / "favicon.svg"
    if fav_file.exists():
        return FileResponse(fav_file, media_type="image/svg+xml")
    return JSONResponse(status_code=204, content=None)


# ============================================================================
# System & Health Endpoints
# ============================================================================

@app.get("/", response_model=SystemResponse)
async def root():
    """System status endpoint."""
    return SystemResponse(
        system="GridTwin",
        status="online"
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
    
    1. Validates the component exists
    2. Applies physical failure scenario & load redistribution
    3. Runs cascade analysis
    4. Performs risk assessment
    5. Invokes optimizer for restoration
    6. Returns complete authoritative scenario state
    """
    try:
        component_id = request.component_id
        grid = get_grid()
        cascade_eng = get_cascade_engine()
        risk_svc = get_risk_service()
        optimizer = get_optimizer()
        
        # Validate component exists
        component_dict = grid.get_component(component_id)
        if not component_dict:
            raise HTTPException(
                status_code=404,
                detail=f"Component {component_id} not found"
            )
        
        # Create unique scenario ID
        scenario_id = f"SCN-{uuid.uuid4().hex[:8].upper()}"
        
        # Apply physical scenario recalculation
        scenario_info = grid.apply_failure_scenario(component_id)
        
        # Get updated serialized grid
        serialized_grid = grid.serialize()
        
        # Extract node categories
        warning_nodes = [
            n for n in serialized_grid.nodes
            if n.id in scenario_info.get("warning", [])
        ]
        overloaded_nodes = [
            n for n in serialized_grid.nodes
            if n.id in scenario_info.get("overloaded", [])
        ]
        disconnected_nodes = [
            n for n in serialized_grid.nodes
            if n.id in scenario_info.get("disconnected", [])
        ]
        
        # Affected components = all non-normal components except the failed one
        affected_nodes = [
            n for n in serialized_grid.nodes
            if n.id != component_id and n.status != "normal"
        ]
        
        # Critical facilities at risk
        critical_at_risk = [
            n for n in serialized_grid.nodes
            if n.is_critical_load and n.status != "normal" and n.id != component_id
        ]
        
        # Affected edges
        affected_edge_ids = set(scenario_info.get("affected_edges", []))
        affected_edges = [
            e for e in serialized_grid.edges
            if e.id in affected_edge_ids or e.status != "normal"
        ]
        
        # Run cascade analysis
        cascade_events: List[CascadeEvent] = cascade_eng.analyze_cascade(component_id)
        
        # Perform risk analysis
        risk_analysis: RiskAnalysis = risk_svc.analyze_risks()
        
        # Run restoration optimizer
        restoration_result = optimizer.optimize_restoration(component_id)
        
        # Compile metrics
        estimated_consumers = int(
            sum(c.load_mw * 1000 for c in affected_nodes)
            if affected_nodes else 0
        )
        metrics = SimulationMetrics(
            components_affected=len(affected_nodes),
            critical_services_at_risk=len(critical_at_risk),
            estimated_consumers_affected=estimated_consumers
        )
        
        failed_node_schema = NodeSchema(**grid.get_component(component_id))
        
        # Build unified response
        response = SimulationResponse(
            scenario_id=scenario_id,
            failed_component=failed_node_schema,
            affected_components=affected_nodes,
            warning_components=warning_nodes,
            overloaded_components=overloaded_nodes,
            disconnected_components=disconnected_nodes,
            critical_loads_at_risk=critical_at_risk,
            affected_edges=affected_edges,
            grid=serialized_grid,
            cascade=cascade_events,
            risk_summary=risk_analysis,
            risk_scores=risk_analysis.risks,
            restoration=restoration_result,
            metrics=metrics
        )
        
        # Store scenario in memory cache
        scenarios[scenario_id] = {
            "timestamp": datetime.now().isoformat(),
            "failed_component": component_id,
            "response": response
        }
        
        logger.info(f"Simulation {scenario_id} completed successfully for {component_id}")
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
        return {
            "status": "success",
            "message": "Grid reset to baseline state",
            "grid": grid.serialize()
        }
    except Exception as e:
        logger.error(f"Reset failed: {e}")
        raise HTTPException(status_code=500, detail="Reset failed")


# ============================================================================
# Development Entry Point
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8001,
        reload=True
    )
