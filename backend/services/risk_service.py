"""
RiskService - GridTwin risk assessment integration boundary.

The scoring engine is Hema's AI Risk & Data module, adapted to consume the
current GridDigitalTwin state instead of Hema's original hardcoded dataset.
This preserves the existing FastAPI/RiskService contract while making
backend/data/grid.json the single source of truth.
"""

from typing import Dict, List, Optional

from core.grid_engine import GridDigitalTwin
from models.grid_schemas import RiskAnalysis, RiskScore
from services.hema_risk_engine import HemaRiskEngine


class RiskService:
    """Expose Hema-derived live-grid risk results through the existing API."""

    def __init__(self, grid: GridDigitalTwin):
        self.grid = grid
        self.engine = HemaRiskEngine(grid)

    @staticmethod
    def _join_reasons(reasons: List[str]) -> str:
        if reasons:
            return "; ".join(reasons)
        return "No elevated Hema risk factors detected"

    def _to_api_risk_score(self, result: Dict) -> RiskScore:
        """
        Convert a Hema result to the established GridTwin RiskScore schema.

        Hema's formula supplies the baseline score. Operational status remains
        authoritative: an already failed component is represented as 100%
        critical risk so existing simulation semantics and tests remain valid.
        """
        component_id = result["id"]
        score = float(result["risk_percentage"])
        level = result["api_risk_level"]
        reasons = list(result.get("reasons", []))

        status = self.grid.get_component_status(component_id) or "normal"
        if status == "failed":
            score = 100.0
            level = "critical"
            reasons.insert(0, "Component has failed")
        elif status == "critical":
            score = max(score, 80.0)
            level = "critical"
            reasons.insert(0, "Component is in critical operational status")
        elif status == "high_risk":
            score = max(score, 60.0)
            level = "high_risk"
            reasons.insert(0, "Component is in high-risk operational status")
        elif status == "warning":
            score = max(score, 40.0)
            if level == "normal":
                level = "warning"
            reasons.insert(0, "Component is in warning operational status")

        return RiskScore(
            component_id=component_id,
            risk_score=min(score, 100.0),
            risk_level=level,
            reason=self._join_reasons(reasons),
            loading_percentage=float(result.get("loading_percentage", 0.0)),
            criticality_score=float(result.get("criticality_score", 0.0)),
            risk_source="hema_ai_risk_module",
        )

    def analyze_risks(self) -> RiskAnalysis:
        """Run Hema's risk analysis against the current grid state."""
        hema_results = self.engine.analyze_grid()
        risk_scores = [self._to_api_risk_score(result) for result in hema_results]
        risk_scores.sort(key=lambda item: item.risk_score, reverse=True)

        next_likely = None
        for score in risk_scores:
            if self.grid.get_component_status(score.component_id) != "failed":
                next_likely = score.component_id
                break

        overall_risk = (
            sum(score.risk_score for score in risk_scores) / len(risk_scores)
            if risk_scores
            else 0.0
        )
        overall_risk = min(overall_risk, 100.0)

        analytics = self._build_analytics(risk_scores, next_likely)

        return RiskAnalysis(
            risks=risk_scores,
            next_likely_component=next_likely,
            overall_risk=overall_risk,
            analytics=analytics,
            risk_source="hema_ai_risk_module",
        )

    def _build_analytics(
        self,
        scores: List[RiskScore],
        next_likely: Optional[str],
    ) -> Dict:
        """Expose Hema-style dashboard counts using API-compatible levels."""
        counts = {
            "critical": 0,
            "high_risk": 0,
            "warning": 0,
            "normal": 0,
        }
        for score in scores:
            counts[score.risk_level] += 1

        highest = scores[0] if scores else None
        return {
            "total_components": len(scores),
            "critical_components": counts["critical"],
            "high_risk_components": counts["high_risk"],
            "warning_components": counts["warning"],
            "healthy_components": counts["normal"],
            "highest_risk_component": highest.component_id if highest else None,
            "highest_risk_score": highest.risk_score if highest else None,
            "predicted_next_component": next_likely,
            "source": "hema_ai_risk_module",
        }

    def get_dashboard_analytics(self) -> Dict:
        """Return current dashboard analytics from Hema-derived risk results."""
        return self.analyze_risks().analytics or {}

    def get_next_likely_failure(self) -> Optional[str]:
        """Return the highest-risk component that has not already failed."""
        return self.analyze_risks().next_likely_component
