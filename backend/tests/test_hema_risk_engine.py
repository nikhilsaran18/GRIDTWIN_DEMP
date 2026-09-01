"""Focused tests for Hema's live-grid risk integration."""

import json
from pathlib import Path

from core.grid_engine import GridDigitalTwin
from services.hema_risk_engine import HemaRiskEngine
from services.risk_service import RiskService


def make_grid() -> GridDigitalTwin:
    dataset = Path(__file__).parent.parent / "data" / "grid.json"
    return GridDigitalTwin(str(dataset))


def test_hema_engine_uses_live_grid_not_hardcoded_dataset():
    grid = make_grid()
    engine = HemaRiskEngine(grid)
    ids = {result["id"] for result in engine.analyze_grid()}

    assert "T8" in ids
    assert "T5" not in ids
    assert ids == set(grid._node_data.keys())


def test_hema_t7_formula_uses_current_capacity_and_load():
    grid = make_grid()
    engine = HemaRiskEngine(grid)
    result = next(item for item in engine.analyze_grid() if item["id"] == "T7")

    # Current grid.json: 8 MW / 10 MW = 80% loading.
    assert result["loading_percentage"] == 80.0
    # Hema formula: criticality 55, then 80*0.5 + 55*0.4 = 62.
    assert result["criticality_score"] == 55
    assert result["risk_percentage"] == 62
    assert result["risk_level"] == "HIGH"


def test_risk_service_exposes_hema_source_and_analytics():
    grid = make_grid()
    service = RiskService(grid)
    analysis = service.analyze_risks()

    assert analysis.risk_source == "hema_ai_risk_module"
    assert analysis.analytics is not None
    assert analysis.analytics["total_components"] == 8
    assert analysis.analytics["source"] == "hema_ai_risk_module"
    assert all(score.risk_source == "hema_ai_risk_module" for score in analysis.risks)


def test_failed_component_keeps_operational_100_percent_semantics():
    grid = make_grid()
    service = RiskService(grid)
    grid.fail_component("T7")

    analysis = service.analyze_risks()
    t7 = next(score for score in analysis.risks if score.component_id == "T7")

    assert t7.risk_score == 100.0
    assert t7.risk_level == "critical"
    assert "Component has failed" in t7.reason
    assert analysis.next_likely_component != "T7"


def test_no_duplicate_hardcoded_grid_in_hema_engine_source():
    source = (Path(__file__).parent.parent / "services" / "hema_risk_engine.py").read_text()
    assert "GRID_COMPONENTS =" not in source
    assert "GRID_CONNECTIONS =" not in source
