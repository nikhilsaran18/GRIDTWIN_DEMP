"""
HemaRiskEngine - Live-grid adapter for Hema's GridTwin AI Risk & Data module.

This module preserves the scoring logic from Hema's standalone risk_analysis.py
while replacing its hardcoded GRID_COMPONENTS / GRID_CONNECTIONS dataset with
the current GridDigitalTwin state.

The authoritative data source remains backend/data/grid.json via GridDigitalTwin.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Sequence, Tuple

from core.grid_engine import GridDigitalTwin


class HemaRiskEngine:
    """Run Hema's risk formulas against the live GridDigitalTwin state."""

    _TYPE_MAP = {
        "source": "Substation",
        "substation": "Substation",
        "transformer": "Transformer",
        "feeder": "Feeder",
        "bus": "Bus",
        "load": "Load",
        "hospital": "Hospital",
        "emergency_service": "Emergency Service",
    }

    _LEVEL_MAP = {
        "CRITICAL": "critical",
        "HIGH": "high_risk",
        "WARNING": "warning",
        "LOW": "normal",
    }

    def __init__(self, grid: GridDigitalTwin):
        self.grid = grid

    def _connections(self) -> List[Tuple[str, str]]:
        """Return live graph connections in Hema's pair format."""
        return [(source, target) for source, target in self.grid.graph.edges()]

    def _component(self, component_id: str, node_data: dict) -> Dict:
        """Translate GridTwin node data to the field names used by Hema's logic."""
        return {
            "id": component_id,
            "type": self._TYPE_MAP.get(
                str(node_data.get("type", "unknown")).lower(),
                str(node_data.get("type", "Unknown")).replace("_", " ").title(),
            ),
            "capacity": float(node_data.get("capacity_mw", 0.0) or 0.0),
            "load": float(node_data.get("load_mw", 0.0) or 0.0),
            "critical": bool(node_data.get("is_critical_load", False)),
            "status": node_data.get("status", "normal"),
        }

    @staticmethod
    def calculate_loading(component: Dict) -> float:
        """Hema's loading-percentage calculation."""
        capacity = float(component.get("capacity", 0.0) or 0.0)
        load = float(component.get("load", 0.0) or 0.0)
        if capacity == 0:
            return 0.0
        return round((load / capacity) * 100.0, 2)

    @classmethod
    def calculate_criticality(
        cls,
        component: Dict,
        connections: Sequence[Tuple[str, str]],
    ) -> Tuple[int, List[str]]:
        """Hema's component criticality formula, unchanged in weighting."""
        score = 0
        reasons: List[str] = []
        component_id = component["id"]

        if component.get("critical"):
            score += 50
            reasons.append("Supplies a critical facility")

        connection_count = sum(
            1 for connection in connections if component_id in connection
        )

        if connection_count >= 3:
            score += 25
            reasons.append(
                f"Highly connected to the grid ({connection_count} connections)"
            )
        elif connection_count == 2:
            score += 15
            reasons.append("Important network connection point")

        if component.get("type") in {"Substation", "Transformer", "Feeder"}:
            score += 20
            reasons.append(
                f"{component['type']} is important for power distribution"
            )

        loading = cls.calculate_loading(component)
        if loading >= 80:
            score += 20
            reasons.append("Operating under high load")
        elif loading >= 60:
            score += 10
            reasons.append("Moderate to high operating load")

        return min(score, 100), reasons

    @classmethod
    def calculate_risk(
        cls,
        component: Dict,
        connections: Sequence[Tuple[str, str]],
    ) -> Dict:
        """Hema's risk formula using a live GridTwin component."""
        loading = cls.calculate_loading(component)
        criticality_score, reasons = cls.calculate_criticality(
            component, connections
        )

        risk = loading * 0.5
        risk += criticality_score * 0.4

        connection_count = sum(
            1 for connection in connections if component["id"] in connection
        )
        if connection_count >= 3:
            risk += 10

        risk = min(round(risk), 100)

        if risk >= 80:
            level = "CRITICAL"
        elif risk >= 60:
            level = "HIGH"
        elif risk >= 40:
            level = "WARNING"
        else:
            level = "LOW"

        return {
            "id": component["id"],
            "type": component["type"],
            "loading_percentage": loading,
            "criticality_score": criticality_score,
            "risk_percentage": risk,
            "risk_level": level,
            "api_risk_level": cls._LEVEL_MAP[level],
            "reasons": reasons,
            "status": component.get("status", "normal"),
        }

    def analyze_grid(self) -> List[Dict]:
        """Analyze every component in the current live grid state."""
        connections = self._connections()
        results = [
            self.calculate_risk(
                self._component(component_id, node_data),
                connections,
            )
            for component_id, node_data in self.grid._node_data.items()
        ]
        results.sort(key=lambda item: item["risk_percentage"], reverse=True)
        return results

    def predict_next_affected_component(self) -> Optional[Dict]:
        """Return Hema's highest-risk currently non-failed component."""
        for result in self.analyze_grid():
            if self.grid.get_component_status(result["id"]) != "failed":
                return result
        return None

    def get_dashboard_analytics(self) -> Dict:
        """Return Hema-style dashboard analytics for the current live grid."""
        results = self.analyze_grid()
        critical = [r for r in results if r["risk_level"] == "CRITICAL"]
        high = [r for r in results if r["risk_level"] == "HIGH"]
        warning = [r for r in results if r["risk_level"] == "WARNING"]
        low = [r for r in results if r["risk_level"] == "LOW"]

        return {
            "total_components": len(results),
            "critical_components": len(critical),
            "high_risk_components": len(high),
            "warning_components": len(warning),
            "healthy_components": len(low),
            "highest_risk": results[0] if results else None,
            "all_components": results,
            "source": "hema_ai_risk_module",
        }
