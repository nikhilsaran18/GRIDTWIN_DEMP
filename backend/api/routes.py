"""
FastAPI Routes for GridTwin Restoration & Optimization.

Decoupled endpoint for upstream integration (Member 1 / Nikhil and frontend).
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from restoration.models import RestorationResult
from restoration.service import RestorationService
from restoration.adapter import MockGridAdapter, NikhilGridAdapter


router = APIRouter(prefix="/restoration", tags=["Restoration & Optimization"])


class OptimizeRestorationRequest(BaseModel):
    failed_components: List[str] = Field(default_factory=lambda: ["T7"], description="List of failed component IDs")
    scenario: Optional[str] = Field(default="benchmark", description="Mock scenario name: benchmark | bottleneck | no_path")
    upstream_grid_payload: Optional[Dict[str, Any]] = Field(default=None, description="Optional raw payload from upstream grid engine")


@router.post(
    "/optimize",
    response_model=RestorationResult,
    status_code=status.HTTP_200_OK,
    summary="Compute Optimal Grid Restoration Strategy",
    description="Analyzes grid failure, discovers alternate paths, validates capacity, solves OR-Tools CP-SAT model, and returns ranked recovery sequence.",
)
async def optimize_grid_restoration(request: OptimizeRestorationRequest) -> RestorationResult:
    try:
        # If upstream data from Nikhil is provided, use NikhilGridAdapter
        if request.upstream_grid_payload:
            adapter = NikhilGridAdapter(request.upstream_grid_payload)
        else:
            adapter = MockGridAdapter(request.scenario or "benchmark")

        service = RestorationService(adapter=adapter)
        result = service.optimize_restoration(failed_components=request.failed_components)
        return result

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Restoration optimization failed: {str(exc)}",
        )
