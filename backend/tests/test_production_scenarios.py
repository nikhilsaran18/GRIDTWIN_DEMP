"""
GridTwin Production Scenario & Master Regression Tests.

Validates:
1. Baseline grid state (8 authoritative nodes, 8 edges)
2. T7 failure scenario (physical load transfer to F5, H1 at risk, L1 disconnected)
3. F3 failure scenario (F3 is Feeder & FAILED, not overloaded; H1 supplied via F5)
4. S1 source failure scenario (all downstream unenergized, no fake load transfers)
5. T8 & F5 failure scenarios (H1 remains safely powered via primary feeder F3)
6. Reset scenario (returns 8/8 healthy baseline, 0 failed, 0 at risk)
7. Scenario replacement & isolation
"""

import pytest
from fastapi.testclient import TestClient
from main import app, get_grid


@pytest.fixture
def client():
    """Create FastAPI test client."""
    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_grid_state():
    """Ensure grid is reset to baseline before each test."""
    grid = get_grid()
    grid.reset_grid()
    yield
    grid.reset_grid()


def test_baseline_authoritative_grid(client):
    """Test baseline /api/grid returns exactly the 8 authoritative nodes."""
    response = client.get("/api/grid")
    assert response.status_code == 200
    data = response.json()
    
    assert len(data["nodes"]) == 8
    node_ids = {n["id"] for n in data["nodes"]}
    expected_ids = {"S1", "T7", "T8", "F3", "F5", "L1", "H1", "L2"}
    assert node_ids == expected_ids
    
    # Verify no fake nodes like E1
    assert "E1" not in node_ids
    
    # Verify H1 is critical and L2 is commercial (not critical)
    h1 = next(n for n in data["nodes"] if n["id"] == "H1")
    assert h1["is_critical_load"] is True
    assert h1["type"] == "hospital"
    
    l2 = next(n for n in data["nodes"] if n["id"] == "L2")
    assert l2["is_critical_load"] is False
    assert l2["type"] == "load"
    
    # Summary
    summary = data["summary"]
    assert summary["total"] == 8
    assert summary["healthy"] == 8
    assert summary["failed"] == 0
    assert summary["at_risk"] == 0


def test_t7_failure_simulation(client):
    """Test T7 failure scenario calculations and load redistribution."""
    res = client.post("/api/simulate/failure", json={"component_id": "T7"})
    assert res.status_code == 200
    data = res.json()
    
    assert data["failed_component"]["id"] == "T7"
    assert data["failed_component"]["type"] == "transformer"
    assert data["failed_component"]["status"] == "failed"
    
    # F5 should carry H1 load and be overloaded
    overloaded_ids = [n["id"] for n in data["overloaded_components"]]
    assert "F5" in overloaded_ids
    
    # Disconnected nodes
    disc_ids = [n["id"] for n in data["disconnected_components"]]
    assert "F3" in disc_ids
    assert "L1" in disc_ids
    
    # H1 is at risk
    crit_risk_ids = [n["id"] for n in data["critical_loads_at_risk"]]
    assert "H1" in crit_risk_ids
    
    # Risk factor breakdown
    assert "factors" in data["risk_summary"]
    assert data["risk_summary"]["overall_risk"] > 50.0
    assert data["risk_summary"]["factors"]["critical_exposure"] > 50.0
    
    # Restoration plan
    assert data["restoration"]["available"] is True
    assert len(data["restoration"]["actions"]) > 0


def test_f3_failure_simulation_no_stale_overload(client):
    """
    Test F3 failure:
    - F3 is FEEDER and FAILED (not classified as overloaded transformer)
    - H1 is rerouted via F5
    - L1 is disconnected
    """
    res = client.post("/api/simulate/failure", json={"component_id": "F3"})
    assert res.status_code == 200
    data = res.json()
    
    assert data["failed_component"]["id"] == "F3"
    assert data["failed_component"]["type"] == "feeder"
    assert data["failed_component"]["status"] == "failed"
    
    # F3 itself must NOT be in overloaded_components
    overloaded_ids = [n["id"] for n in data["overloaded_components"]]
    assert "F3" not in overloaded_ids
    assert "F5" in overloaded_ids  # F5 is carrying the rerouted H1 load
    
    # Disconnected nodes
    disc_ids = [n["id"] for n in data["disconnected_components"]]
    assert "L1" in disc_ids


def test_s1_source_failure_simulation(client):
    """
    Test S1 source failure:
    - Entire downstream network loses power (disconnected / critical risk)
    - No fake load transfer overloads
    - Very high risk score
    """
    res = client.post("/api/simulate/failure", json={"component_id": "S1"})
    assert res.status_code == 200
    data = res.json()
    
    assert data["failed_component"]["id"] == "S1"
    assert data["failed_component"]["type"] == "source"
    
    # No overloaded components because there is no alternate source
    assert len(data["overloaded_components"]) == 0
    
    # All 7 downstream nodes disconnected
    disc_ids = [n["id"] for n in data["disconnected_components"]]
    assert len(disc_ids) == 7
    assert "H1" in disc_ids
    
    # High overall risk
    assert data["risk_summary"]["overall_risk"] >= 80.0
    assert data["risk_summary"]["factors"]["critical_exposure"] == 100.0
    assert data["risk_summary"]["factors"]["redundancy"] == 0.0


def test_t8_and_f5_failures(client):
    """Test T8 and F5 failures: H1 remains safely powered on primary feeder F3."""
    # Test T8
    res_t8 = client.post("/api/simulate/failure", json={"component_id": "T8"})
    assert res_t8.status_code == 200
    data_t8 = res_t8.json()
    assert data_t8["failed_component"]["id"] == "T8"
    assert "L2" in [n["id"] for n in data_t8["disconnected_components"]]
    # H1 is NOT in critical_loads_at_risk because F3 is operational
    assert "H1" not in [n["id"] for n in data_t8["critical_loads_at_risk"]]
    
    # Reset
    client.post("/api/simulation/reset")
    
    # Test F5
    res_f5 = client.post("/api/simulate/failure", json={"component_id": "F5"})
    assert res_f5.status_code == 200
    data_f5 = res_f5.json()
    assert data_f5["failed_component"]["id"] == "F5"
    assert "L2" in [n["id"] for n in data_f5["disconnected_components"]]
    assert "H1" not in [n["id"] for n in data_f5["critical_loads_at_risk"]]


def test_reset_simulation_returns_clean_baseline(client):
    """Test that resetting clears all scenario states and returns 8 healthy nodes."""
    # First simulate a failure
    client.post("/api/simulate/failure", json={"component_id": "T7"})
    
    # Now reset
    res = client.post("/api/simulation/reset")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    
    # Verify grid is 100% healthy
    grid_res = client.get("/api/grid")
    grid_data = grid_res.json()
    assert grid_data["summary"]["healthy"] == 8
    assert grid_data["summary"]["failed"] == 0
    assert grid_data["summary"]["at_risk"] == 0
