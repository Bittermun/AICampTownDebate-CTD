"""
Response Models: Pydantic models for validated LLM responses.
These enforce schema validation at the LLM boundary, eliminating parsing heuristics.
"""
from pydantic import BaseModel, Field, model_validator


class JudgmentResponse(BaseModel):
    """Validated response from judge models."""
    confidence_a: float = Field(ge=0.0, le=1.0, description="Confidence score for Debater A")
    confidence_b: float = Field(ge=0.0, le=1.0, description="Confidence score for Debater B")
    reasoning: str = Field(min_length=1, description="Explanation of the judgment")
    
    @model_validator(mode='after')
    def normalize_confidences(self):
        """Ensure confidences sum to 1.0."""
        total = self.confidence_a + self.confidence_b
        if total > 0:
            object.__setattr__(self, 'confidence_a', self.confidence_a / total)
            object.__setattr__(self, 'confidence_b', self.confidence_b / total)
        return self


class MultiDimensionJudgment(BaseModel):
    """Multi-dimension judgment for nuanced evaluation.
    
    Scores each debater on 3 dimensions:
    - accuracy: Factual correctness, evidence quality
    - responsiveness: Addressed opponent's specific points
    - development: Improved/refined argument over time
    
    Passive debaters naturally score low on responsiveness + development.
    """
    accuracy_a: float = Field(ge=0.0, le=1.0, description="A's factual accuracy")
    accuracy_b: float = Field(ge=0.0, le=1.0, description="B's factual accuracy")
    responsiveness_a: float = Field(ge=0.0, le=1.0, description="A's engagement with B's points")
    responsiveness_b: float = Field(ge=0.0, le=1.0, description="B's engagement with A's points")
    development_a: float = Field(ge=0.0, le=1.0, description="A's argument refinement")
    development_b: float = Field(ge=0.0, le=1.0, description="B's argument refinement")
    reasoning: str = Field(min_length=1, default="No reasoning provided by judge.", description="Explanation of scoring")
    
    @model_validator(mode='before')
    @classmethod
    def coerce_reasoning_to_string(cls, data: dict):
        if 'reasoning' in data and not isinstance(data['reasoning'], str):
            import json
            data['reasoning'] = json.dumps(data['reasoning'])
        return data

    def weighted_confidence(self, weights: dict = None, spread_factor: float = 0.4) -> tuple[float, float]:
        """Calculate weighted confidence scores from dimensions."""
        if weights is None:
            weights = {"accuracy": 0.4, "responsiveness": 0.3, "development": 0.3}
        
        raw_a = (
            weights["accuracy"] * self.accuracy_a +
            weights["responsiveness"] * self.responsiveness_a +
            weights["development"] * self.development_a
        )
        raw_b = (
            weights["accuracy"] * self.accuracy_b +
            weights["responsiveness"] * self.responsiveness_b +
            weights["development"] * self.development_b
        )
        
        # Margin-based scoring preserves the gap between raw scores
        margin = raw_a - raw_b
        conf_a = 0.5 + (margin * spread_factor)
        conf_b = 1.0 - conf_a
        
        # Clamp to 5-95% range
        conf_a = max(0.05, min(0.95, conf_a))
        conf_b = max(0.05, min(0.95, conf_b))
        
        return conf_a, conf_b


class DeliberationResponse(BaseModel):
    """Validated response from debater deliberation."""
    reasoning: str = Field(min_length=1, description="Strategic justification for the decision")
    decision: str = Field(pattern=r'^(?i)(RESPOND|PASS)$', description="Strategic choice")
    amount: float = Field(ge=0.0, description="Token amount to bet")
    max_budget: float = Field(ge=0.0, le=200.0, default=30.0, description="Maximum tokens authorized for generating the response")
    use_search: bool = Field(default=False, description="Whether to pay for a web search as part of the response")
