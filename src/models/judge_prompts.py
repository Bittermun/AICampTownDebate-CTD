"""
New judge prompt template for multi-dimension scoring.
This file contains the prompt that will replace the current single-score prompt.
"""

MULTI_DIMENSION_SYSTEM = """You are an impartial debate judge scoring on 3 dimensions.

For each dimension, allocate 100 points between Debater A and Debater B.
  - accuracy_split = points going to A for factual correctness / logical soundness
  - responsiveness_split = points going to A for directly addressing opponent claims
  - development_split = points going to A for improving / updating prior arguments
  B always receives (100 - split) points on each dimension.

Allocation guidelines:
  - A clearly stronger: 65-80 to winner
  - Slight edge: 55-65 to winner
  - Genuine tie on a dimension: 50 (rare — only if truly indistinguishable)
  - One side completely failed: 80-95 to winner

IMPORTANT: You must choose a winner on each dimension.
Splitting 50/50 on every dimension means you found NO winner anywhere — justify
this explicitly in reasoning if you genuinely believe it.

Score only from the text provided. Keep reasoning concise and specific.
Respond ONLY with valid JSON."""

MULTI_DIMENSION_PROMPT = """Topic: {topic}

--- Argument {first_label} ---
{first_arg}

--- Argument {second_label} ---
{second_arg}

{prior_context}Allocate 100 points per dimension between the two debaters.
accuracy_split / responsiveness_split / development_split = points going to {first_label}.
{second_label} receives (100 - split) on each dimension.

{{
  "reasoning": "dimension-by-dimension explanation citing specific claims",
  "accuracy_split": 0-100,
  "responsiveness_split": 0-100,
  "development_split": 0-100
}}"""

# Example of expected output (allocation format — A gets split %, B gets 100-split %):
EXAMPLE_OUTPUT = """
{
  "reasoning": "A: solid evidence, directly addressed B's core claim about X, refined position. B: made unsupported claim about Y, did not respond to A's refutation, argument static.",
  "accuracy_split": 70,
  "responsiveness_split": 80,
  "development_split": 70
}
"""

# Injected into MULTI_DIMENSION_PROMPT as {prior_context} when prior round data is available.
# Enables the judge to detect and penalize stagnation across debate iterations.
COMPARATIVE_CONTEXT_BLOCK = """--- Prior Round Scores ---
Previous confidence: A={prior_conf_a:.0%}, B={prior_conf_b:.0%}  (gap: {prior_gap:.0%})

CONTEXT: These are scores from the PREVIOUS iteration of this debate.
- If an argument is substantively the same as before, cap DEVELOPMENT split at 30 (out of 100).
- If an argument directly rebuts a prior weakness, reward development (70+ out of 100).

"""
