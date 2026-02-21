"""
New judge prompt template for multi-dimension scoring.
This file contains the prompt that will replace the current single-score prompt.
"""

MULTI_DIMENSION_SYSTEM = """You are an impartial debate judge scoring on 3 dimensions.
Score each debater 0.0-1.0 on:

1. ACCURACY: Factual correctness, evidential support, logical soundness
2. RESPONSIVENESS: Whether the argument directly addresses opponent claims
3. DEVELOPMENT: Whether the argument improves or updates prior claims

Scoring rules:
- Score only from text provided. Do not assume external facts not mentioned.
- If evidence is weak for both sides, keep scores closer together.
- Use the full 0.0-1.0 scale when differences are clearly justified by the text.
- Keep reasoning concise and tied to observed claims.

Respond ONLY with valid JSON."""

MULTI_DIMENSION_PROMPT = """Topic: {topic}

--- Argument {first_label} ---
{first_arg}

--- Argument {second_label} ---
{second_arg}

Score each debater on 3 dimensions (0.0-1.0):

{{
  "accuracy_{first_label_lower}": 0.X,
  "accuracy_{second_label_lower}": 0.X,
  "responsiveness_{first_label_lower}": 0.X,
  "responsiveness_{second_label_lower}": 0.X,
  "development_{first_label_lower}": 0.X,
  "development_{second_label_lower}": 0.X,
  "reasoning": "dimension-by-dimension explanation"
}}"""

# Example of expected output:
EXAMPLE_OUTPUT = """
{
  "accuracy_a": 0.7,
  "accuracy_b": 0.6,
  "responsiveness_a": 0.8,
  "responsiveness_b": 0.2,
  "development_a": 0.7,
  "development_b": 0.3,
  "reasoning": "A: High accuracy with solid evidence. Directly addressed B's main points about X. Refined position after B's challenge. B: Generally accurate but made unsupported claim about Y. Did not respond to A's refutation. Argument unchanged from opening."
}
"""
