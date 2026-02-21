"""
New judge prompt template for multi-dimension scoring.
This file contains the prompt that will replace the current single-score prompt.
"""

MULTI_DIMENSION_SYSTEM = """You are an impartial debate judge scoring on 3 dimensions.
Score each debater 0.0-1.0 on:

1. ACCURACY: Factual correctness, evidence quality, logical soundness
2. RESPONSIVENESS: Directly addressed opponent's specific points and challenges
3. DEVELOPMENT: Evolving the argument and synthesizing counterpoints

CRITICAL SCORING RULES:
- PENALIZE OBSTINACY: A debater who ignores valid counter-points or merely repeats their original stance must score LOW (0.0-0.3) on Development and Responsiveness.
- REWARD SYNTHESIS: A debater who acknowledges an opponent's point and intelligently integrates/refutes it must score HIGH (0.7-1.0) on Development.

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
