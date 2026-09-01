"""
RiskService - Risk assessment and prediction for grid components.

FALLBACK IMPLEMENTATION: This is a clearly marked fallback risk service
that can be replaced without changing the API. If Hema's actual AI/risk
module is integrated, this should be replaced with that implementation.

This fallback uses heuristic risk scoring based on:
- Component loading (high load = higher risk)
- Dependency count (many dependents = higher risk)
- Critical facility exposure (close to critical loads = higher risk)
- Network centrality (central components = higher risk)
- Redundancy availability (low redundancy = higher risk)
"""

from typing import List, Optional
from models.grid_schemas import RiskAnalysis, RiskScore
from core.grid_engine import GridDigitalTwin


class RiskService:
    """
    FALLBACK risk assessment engine.
    
    Provides heuristic risk scoring. Designed to be replaced
    by ML-based module without API changes.
    """
    
    def __init__(self, grid: GridDigitalTwin):
        """
        Initialize RiskService.
        
        Args:
            grid: GridDigitalTwin instance
        """
        self.grid = grid
    
    def analyze_risks(self) -> RiskAnalysis:
        """
        Perform risk analysis on current grid state.
        
        Returns:
            RiskAnalysis with component risk scores
        """
        risk_scores: List[RiskScore] = []
        
        # Analyze each component
        for node_id, node_data in self.grid._node_data.items():
            risk_score = self._calculate_component_risk(node_id, node_data)
            risk_scores.append(risk_score)
        
        # Sort by risk score (highest first)
        risk_scores.sort(key=lambda x: x.risk_score, reverse=True)
        
        # Find next likely component (highest risk non-failed)
        next_likely = None
        for score in risk_scores:
            if self.grid.get_component_status(score.component_id) != "failed":
                next_likely = score.component_id
                break
        
        # Calculate overall system risk
        overall_risk = sum(
            score.risk_score for score in risk_scores
        ) / len(risk_scores) if risk_scores else 0.0
        overall_risk = min(overall_risk, 100.0)
        
        return RiskAnalysis(
            risks=risk_scores,
            next_likely_component=next_likely,
            overall_risk=overall_risk
        )
    
    def _calculate_component_risk(
        self,
        component_id: str,
        node_data: dict
    ) -> RiskScore:
        """
        Calculate risk score for a single component (0-100).
        
        Risk factors:
        - Loading: 0-40 points (40% at >90% capacity)
        - Dependency: 0-30 points (more dependents = higher risk)
        - Centrality: 0-20 points (central components higher risk)
        - Criticality: 0-10 points (inverse - lower criticality higher risk)
        
        Args:
            component_id: Component ID
            node_data: Component data dict
            
        Returns:
            RiskScore object
        """
        risk = 0.0
        reasons: List[str] = []
        
        # Factor 1: Loading (0-40)
        load_pct = self.grid.calculate_load_percentage(component_id)
        loading_risk = (load_pct / 100.0) * 40.0
        risk += loading_risk
        if load_pct > 80:
            reasons.append(f"High load: {load_pct:.1f}%")
        
        # Factor 2: Dependents (0-30)
        dependents = list(self.grid.graph.successors(component_id))
        dependency_risk = min(len(dependents) * 3.5, 30.0)
        risk += dependency_risk
        if len(dependents) > 2:
            reasons.append(f"High dependency: {len(dependents)} downstream")
        
        # Factor 3: Network centrality (0-20)
        # Simple heuristic: transformers more central than feeders, etc.
        comp_type = node_data.get("type", "unknown")
        type_centrality = {
            "source": 0.9,
            "substation": 0.8,
            "transformer": 0.7,
            "feeder": 0.4,
            "bus": 0.6,
            "load": 0.1,
            "hospital": 0.3,
            "emergency_service": 0.3,
        }
        centrality_factor = type_centrality.get(comp_type, 0.5)
        centrality_risk = centrality_factor * 20.0
        risk += centrality_risk
        
        # Factor 4: Criticality inverse (0-10)
        # Lower criticality = higher risk (redundant systems matter less)
        criticality = node_data.get("criticality", 0.5)
        criticality_risk = (1.0 - criticality) * 10.0
        risk += criticality_risk
        
        # Factor 5: Status modifier
        status = node_data.get("status", "normal")
        if status == "failed":
            risk = 100.0
            reasons = ["Component has failed"]
        elif status == "critical":
            risk = min(risk + 30, 100.0)
            reasons.append("Component in critical status")
        elif status == "warning":
            risk = min(risk + 15, 100.0)
            reasons.append("Component in warning status")
        
        # Determine risk level
        if risk >= 80:
            risk_level = "critical"
        elif risk >= 60:
            risk_level = "high_risk"
        elif risk >= 40:
            risk_level = "warning"
        else:
            risk_level = "normal"
        
        reason_text = "; ".join(reasons) if reasons else f"Base load {load_pct:.1f}%"
        
        return RiskScore(
            component_id=component_id,
            risk_score=min(risk, 100.0),
            risk_level=risk_level,
            reason=reason_text
        )
    
    def get_next_likely_failure(self) -> Optional[str]:
        """
        Predict the next component most likely to fail.
        
        Returns:
            Component ID of highest risk non-failed component, or None
        """
        analysis = self.analyze_risks()
        return analysis.next_likely_component
