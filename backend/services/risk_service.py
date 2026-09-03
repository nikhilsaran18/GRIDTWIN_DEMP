"""
RiskService - GridTwin risk assessment integration boundary.

The scoring engine is Hema's AI Risk & Data module, adapted to consume the
current GridDigitalTwin state instead of Hema's original hardcoded dataset.
This preserves the existing FastAPI/RiskService contract while making
backend/data/grid.json the single source of truth.
"""

from typing import Dict, List, Optional

from core.grid_engine import GridDigitalTwin
from models.grid_schemas import RiskAnalysis, RiskScore, RiskFactorBreakdown
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
        elif status in ["critical", "critical_risk"]:
            score = max(score, 95.0)
            level = "critical"
            reasons.insert(0, "Critical facility supply disrupted")
        elif status == "high_risk":
            score = max(score, 60.0)
            level = "high_risk"
            reasons.insert(0, "Component is in high-risk operational status")
        elif status == "overloaded":
            score = max(score, 85.0)
            level = "critical"
            reasons.insert(0, "Component exceeds rated thermal capacity")
        elif status in ["warning", "at_risk"]:
            score = max(score, 55.0)
            if level == "normal":
                level = "warning"
            reasons.insert(0, "Component is under elevated stress / alternate path reliance")
        elif status == "disconnected":
            # If source is failed, disconnected assets are fully unenergized
            is_blackout = (self.grid.get_component_status("S1") == "failed")
            score = max(score, 85.0 if is_blackout else 70.0)
            level = "critical" if is_blackout else "high_risk"
            reasons.insert(0, "Component is disconnected from power supply")

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

        # Compute scenario-specific risk breakdown factors
        factors = self._compute_factors(risk_scores)

        analytics = self._build_analytics(risk_scores, next_likely)

        return RiskAnalysis(
            risks=risk_scores,
            next_likely_component=next_likely,
            overall_risk=round(overall_risk, 1),
            analytics=analytics,
            factors=factors,
            risk_source="hema_ai_risk_module",
        )

    def _compute_factors(self, scores: List[RiskScore]) -> RiskFactorBreakdown:
        """Calculate dynamic factor breakdown based on actual current grid state."""
        # 1. Component Loading: Average/peak loading of active components
        active_loadings = [
            s.loading_percentage for s in scores
            if s.loading_percentage is not None and self.grid.get_component_status(s.component_id) != "failed"
        ]
        avg_loading = sum(active_loadings) / len(active_loadings) if active_loadings else 0.0
        peak_loading = max(active_loadings) if active_loadings else 0.0
        component_loading_factor = round((avg_loading * 0.4 + peak_loading * 0.6), 1)

        # 2. Network Dependency: Ratio of affected/disconnected/strained nodes
        failed_count = sum(1 for s in scores if self.grid.get_component_status(s.component_id) == "failed")
        disc_count = sum(1 for s in scores if self.grid.get_component_status(s.component_id) in ["disconnected", "critical_risk"])
        warn_count = sum(1 for s in scores if self.grid.get_component_status(s.component_id) in ["warning", "overloaded", "at_risk"])
        
        total = len(scores) or 1
        dependency_factor = round(min(100.0, ((failed_count * 30 + disc_count * 20 + warn_count * 15) / total) * 1.5 + 20.0), 1)
        if failed_count == 0:
            dependency_factor = 24.0

        # 3. Critical Exposure: Hospital H1 state
        h1_status = self.grid.get_component_status("H1")
        if h1_status in ["critical_risk", "disconnected", "failed"]:
            critical_exposure = 100.0
        elif h1_status in ["at_risk", "warning", "overloaded"]:
            critical_exposure = 82.0
        else:
            critical_exposure = 15.0

        # 4. Redundancy: Available alternate supply headroom
        f5_status = self.grid.get_component_status("F5")
        t8_status = self.grid.get_component_status("T8")
        s1_status = self.grid.get_component_status("S1")
        if s1_status == "failed":
            redundancy = 0.0
        elif f5_status in ["overloaded", "warning"] or t8_status in ["warning", "overloaded"]:
            redundancy = 38.0
        elif f5_status == "failed" or t8_status == "failed":
            redundancy = 25.0
        elif failed_count > 0:
            redundancy = 45.0
        else:
            redundancy = 88.0

        return RiskFactorBreakdown(
            component_loading=component_loading_factor,
            network_dependency=dependency_factor,
            critical_exposure=critical_exposure,
            redundancy=redundancy
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
