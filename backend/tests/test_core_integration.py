"""
Integration tests for GridTwin core components.

Tests the integration of:
- GridDigitalTwin (graph engine)
- CascadeEngine (cascade analysis)
- RiskService (risk assessment)
- OptimizerAdapter (restoration bridge)
- FastAPI main application
"""

import pytest
import json
from pathlib import Path
from unittest.mock import Mock, patch

from core.grid_engine import GridDigitalTwin
from core.cascade_engine import CascadeEngine
from services.risk_service import RiskService
from services.optimizer_adapter import OptimizerAdapter
from models.grid_schemas import (
    GridResponse,
    CascadeEvent,
    RiskScore,
    RiskAnalysis,
)


@pytest.fixture
def grid():
    """Create a GridDigitalTwin instance for testing."""
    dataset_path = Path(__file__).parent.parent / "data" / "grid.json"
    return GridDigitalTwin(dataset_path=str(dataset_path))


@pytest.fixture
def cascade_engine(grid):
    """Create a CascadeEngine instance for testing."""
    return CascadeEngine(grid)


@pytest.fixture
def risk_service(grid):
    """Create a RiskService instance for testing."""
    return RiskService(grid)


@pytest.fixture
def optimizer_adapter(grid):
    """Create an OptimizerAdapter instance for testing."""
    return OptimizerAdapter(grid)


class TestGridDigitalTwin:
    """Tests for GridDigitalTwin class."""
    
    def test_grid_loads_dataset(self, grid):
        """Test that grid loads dataset correctly."""
        assert len(grid._node_data) == 8
        assert len(grid._edge_data) == 8
        assert "T7" in grid._node_data
        assert "S1" in grid._node_data
    
    def test_get_component(self, grid):
        """Test getting component by ID."""
        t7 = grid.get_component("T7")
        assert t7 is not None
        assert t7["id"] == "T7"
        assert t7["type"] == "transformer"
        assert t7["status"] == "normal"
    
    def test_get_nonexistent_component(self, grid):
        """Test getting non-existent component returns None."""
        result = grid.get_component("T99")
        assert result is None
    
    def test_get_component_status(self, grid):
        """Test getting component status."""
        status = grid.get_component_status("T7")
        assert status == "normal"
    
    def test_set_component_status(self, grid):
        """Test setting component status."""
        result = grid.set_component_status("T7", "warning")
        assert result is True
        assert grid.get_component_status("T7") == "warning"
    
    def test_fail_component(self, grid):
        """Test marking component as failed."""
        result = grid.fail_component("T7")
        assert result is True
        assert grid.get_component_status("T7") == "failed"
    
    def test_fail_nonexistent_component(self, grid):
        """Test failing non-existent component returns False."""
        result = grid.fail_component("T99")
        assert result is False
    
    def test_reset_grid(self, grid):
        """Test resetting grid to baseline."""
        # Fail a component
        grid.fail_component("T7")
        assert grid.get_component_status("T7") == "failed"
        
        # Reset
        grid.reset_grid()
        assert grid.get_component_status("T7") == "normal"
    
    def test_calculate_load_percentage(self, grid):
        """Test load percentage calculation."""
        # T7 has 8.0 MW load and 10.0 MW capacity
        pct = grid.calculate_load_percentage("T7")
        assert pct == pytest.approx(80.0, rel=0.1)
        
        # H1 has 2.5 MW load and 3.0 MW capacity
        pct = grid.calculate_load_percentage("H1")
        assert pct == pytest.approx(83.3, rel=0.1)
    
    def test_identify_critical_facilities(self, grid):
        """Test identifying critical facilities."""
        critical = grid.identify_critical_facilities()
        assert "H1" in critical
        assert len(critical) >= 1
    
    def test_get_network_summary(self, grid):
        """Test getting grid summary."""
        summary = grid.get_network_summary()
        assert summary.total == 8
        assert summary.healthy == 8
        assert summary.failed == 0
        assert summary.at_risk == 0
        assert summary.total_load_mw > 0
    
    def test_serialize_grid(self, grid):
        """Test grid serialization."""
        response = grid.serialize()
        assert isinstance(response, GridResponse)
        assert len(response.nodes) == 8
        assert len(response.edges) == 8
        assert response.summary.total == 8
    
    def test_calculate_connectivity(self, grid):
        """Test calculating reachable nodes from source."""
        # From S1 should reach multiple nodes
        reachable = grid.calculate_connectivity("S1")
        assert "S1" in reachable
        assert "T7" in reachable or "T8" in reachable


class TestCascadeEngine:
    """Tests for CascadeEngine class."""
    
    def test_cascade_analysis_single_failure(self, cascade_engine, grid):
        """Test cascade analysis for single component failure."""
        events = cascade_engine.analyze_cascade("T7")
        
        assert len(events) > 0
        assert events[0].component == "T7"
        assert events[0].event == "FAILED"
        assert events[0].step == 1
    
    def test_cascade_invalid_component(self, cascade_engine):
        """Test cascade analysis for non-existent component."""
        events = cascade_engine.analyze_cascade("T99")
        assert len(events) == 0
    
    def test_get_secondary_vulnerabilities(self, cascade_engine):
        """Test identifying secondary vulnerabilities."""
        vulns = cascade_engine.get_secondary_vulnerabilities("T7")
        assert "overloaded" in vulns
        assert "disconnected" in vulns
        assert "at_risk_critical" in vulns


class TestRiskService:
    """Tests for RiskService class."""
    
    def test_analyze_risks(self, risk_service):
        """Test risk analysis."""
        analysis = risk_service.analyze_risks()
        assert isinstance(analysis, RiskAnalysis)
        assert len(analysis.risks) > 0
        assert all(isinstance(r, RiskScore) for r in analysis.risks)
        assert 0 <= analysis.overall_risk <= 100
    
    def test_risk_scores_range(self, risk_service):
        """Test that risk scores are in valid range."""
        analysis = risk_service.analyze_risks()
        for risk in analysis.risks:
            assert 0 <= risk.risk_score <= 100
            assert risk.risk_level in ["normal", "warning", "high_risk", "critical"]
    
    def test_get_next_likely_failure(self, risk_service):
        """Test predicting next likely failure."""
        next_component = risk_service.get_next_likely_failure()
        # Should return a component ID or None
        assert next_component is None or isinstance(next_component, str)
    
    def test_failed_component_highest_risk(self, risk_service, grid):
        """Test that failed components have highest risk."""
        # Fail a component
        grid.fail_component("T7")
        
        analysis = risk_service.analyze_risks()
        t7_risk = next((r for r in analysis.risks if r.component_id == "T7"), None)
        
        assert t7_risk is not None
        assert t7_risk.risk_score == 100.0
        assert t7_risk.risk_level == "critical"


class TestOptimizerAdapter:
    """Tests for OptimizerAdapter class."""
    
    def test_adapter_initialization(self, optimizer_adapter):
        """Test optimizer adapter initializes."""
        assert optimizer_adapter is not None
    
    def test_is_available(self, optimizer_adapter):
        """Test checking optimizer availability."""
        available = optimizer_adapter.is_available()
        assert isinstance(available, bool)
    
    def test_optimize_restoration(self, optimizer_adapter):
        """Test restoration optimization."""
        result = optimizer_adapter.optimize_restoration("T7")
        assert result.available is not None
        assert result is not None


class TestGridIntegration:
    """Integration tests combining multiple components."""
    
    def test_failure_to_cascade_to_risk(self, grid, cascade_engine, risk_service):
        """Test complete flow: fail -> cascade -> risk."""
        # Fail component
        grid.fail_component("T7")
        
        # Analyze cascade
        events = cascade_engine.analyze_cascade("T7")
        assert events[0].event == "FAILED"
        
        # Analyze risk
        analysis = risk_service.analyze_risks()
        t7_risk = next(r for r in analysis.risks if r.component_id == "T7")
        assert t7_risk.risk_score == 100.0
    
    def test_full_simulation_flow(self, grid, cascade_engine, risk_service, optimizer_adapter):
        """Test complete simulation flow."""
        component_id = "T7"
        
        # 1. Validate component
        component = grid.get_component(component_id)
        assert component is not None
        
        # 2. Fail component
        grid.fail_component(component_id)
        
        # 3. Analyze cascade
        cascade_events = cascade_engine.analyze_cascade(component_id)
        assert len(cascade_events) > 0
        
        # 4. Analyze risk
        risk_analysis = risk_service.analyze_risks()
        assert len(risk_analysis.risks) > 0
        
        # 5. Optimization
        restoration = optimizer_adapter.optimize_restoration(component_id)
        assert restoration is not None
        
        # 6. Reset
        grid.reset_grid()
        assert grid.get_component_status(component_id) == "normal"


class TestAPIIntegration:
    """Test FastAPI endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create FastAPI test client."""
        from fastapi.testclient import TestClient
        from main import app
        return TestClient(app)
    
    def test_root_endpoint(self, client):
        """Test GET / endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["system"] == "GridTwin"
        assert data["status"] == "online"
    
    def test_health_endpoint(self, client):
        """Test GET /health endpoint."""
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert "simulation_engine" in data
        assert "risk_engine" in data
        assert "optimizer" in data
    
    def test_grid_endpoint(self, client):
        """Test GET /api/grid endpoint."""
        response = client.get("/api/grid")
        assert response.status_code == 200
        data = response.json()
        assert "nodes" in data
        assert "edges" in data
        assert "summary" in data
        assert len(data["nodes"]) > 0
    
    def test_component_endpoint(self, client):
        """Test GET /api/components/{id} endpoint."""
        response = client.get("/api/components/T7")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "T7"
    
    def test_failure_simulation_endpoint(self, client):
        """Test POST /api/simulate/failure endpoint."""
        response = client.post(
            "/api/simulate/failure",
            json={"component_id": "T7"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "scenario_id" in data
        assert data["failed_component"]["id"] == "T7"
        assert "cascade" in data
        assert "risk_summary" in data
    
    def test_reset_endpoint(self, client):
        """Test POST /api/simulation/reset endpoint."""
        # First simulate a failure
        client.post("/api/simulate/failure", json={"component_id": "T7"})
        
        # Then reset
        response = client.post("/api/simulation/reset")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
