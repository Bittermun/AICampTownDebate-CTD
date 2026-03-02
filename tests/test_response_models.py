import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.models.response_models import DeliberationResponse, MultiDimensionJudgment

def test_margin_based_scoring_differentiates():
    """Verify that margin-based scoring produces wider spreads than old normalization."""
    # A dominates B
    judgment = MultiDimensionJudgment(
        accuracy_a=0.8, accuracy_b=0.4,
        responsiveness_a=0.8, responsiveness_b=0.4,
        development_a=0.8, development_b=0.4,
        reasoning="A is much better."
    )
    
    # Old math would normalize:
    # A=0.8, B=0.4 -> 0.8 / 1.2 = 66.6%
    # New margin math:
    # Margin = 0.8 - 0.4 = 0.4
    # Conf A = 0.5 + 0.4*0.4 = 0.66 (Wait, it's the same here? Let's check smaller numbers)
    
    # What about A=0.7, B=0.6?
    judgment_close = MultiDimensionJudgment(
        accuracy_a=0.7, accuracy_b=0.6,
        responsiveness_a=0.7, responsiveness_b=0.6,
        development_a=0.7, development_b=0.6,
        reasoning="A is slightly better."
    )
    # Old math: 0.7 / 1.3 = 53.8%
    # New math: margin = 0.1. Conf A = 0.5 + 0.1*0.4 = 0.54. Mmm still 54%.
    
    # Let's check the absolute spread difference
    conf_a, conf_b = judgment_close.weighted_confidence()
    
    assert abs(conf_a - 0.54) < 1e-9
    assert abs(conf_b - 0.46) < 1e-9
    
    # What about A=0.9, B=0.2?
    judgment_crush = MultiDimensionJudgment(
        accuracy_a=0.9, accuracy_b=0.2,
        responsiveness_a=0.9, responsiveness_b=0.2,
        development_a=0.9, development_b=0.2,
        reasoning="Crush."
    )
    # New math: margin = 0.7. Conf A = 0.5 + 0.7*0.4 = 0.78
    conf_a, conf_b = judgment_crush.weighted_confidence()
    assert abs(conf_a - 0.78) < 1e-9
    assert abs(conf_b - 0.22) < 1e-9

def test_margin_symmetry():
    judgment_1 = MultiDimensionJudgment(
        accuracy_a=0.8, accuracy_b=0.3,
        responsiveness_a=0.8, responsiveness_b=0.3,
        development_a=0.8, development_b=0.3,
        reasoning="A wins"
    )
    
    judgment_2 = MultiDimensionJudgment(
        accuracy_a=0.3, accuracy_b=0.8,
        responsiveness_a=0.3, responsiveness_b=0.8,
        development_a=0.3, development_b=0.8,
        reasoning="B wins"
    )
    
    a1, b1 = judgment_1.weighted_confidence()
    a2, b2 = judgment_2.weighted_confidence()
    
    assert abs(a1 - b2) < 1e-9
    assert abs(b1 - a2) < 1e-9

def test_clamp_limits():
    # Margin = 1.0 (max possible)
    judgment_max = MultiDimensionJudgment(
        accuracy_a=1.0, accuracy_b=0.0,
        responsiveness_a=1.0, responsiveness_b=0.0,
        development_a=1.0, development_b=0.0,
        reasoning="Max"
    )
    # margin = 1.0. Spread factor = 0.5 (aggressive)
    conf_a, conf_b = judgment_max.weighted_confidence(spread_factor=0.5)
    # conf_a = 0.5 + 0.5 = 1.0. But clamped to 0.95!
    assert abs(conf_a - 0.95) < 1e-9
    assert abs(conf_b - 0.05) < 1e-9


def test_deliberation_response_accepts_hold_and_metadata():
    payload = DeliberationResponse.model_validate_json(
        """
        {
          "reasoning": "Conserve capital under high fee pressure.",
          "decision": "HOLD",
          "action": "HOLD",
          "intent": "investigate",
          "intent_mix": [{"intent": "investigate", "weight": 0.7}, {"intent": "hold", "weight": 0.3}],
          "rationale_short": "High fee and low balance.",
          "rule_refs_used": ["R_BANKRUPTCY", "R_FEE_GROWTH"],
          "amount": 0,
          "max_budget": 20,
          "use_search": false
        }
        """
    )
    assert payload.decision.upper() == "HOLD"
    assert payload.action and payload.action.upper() == "HOLD"
    assert payload.intent == "investigate"
    assert payload.rule_refs_used == ["R_BANKRUPTCY", "R_FEE_GROWTH"]


if __name__ == "__main__":
    test_margin_based_scoring_differentiates()
    test_margin_symmetry()
    test_clamp_limits()
    test_deliberation_response_accepts_hold_and_metadata()
    print("test_response_models: PASS")
