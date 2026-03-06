"""Tests that the economic awareness injection (Session 26) is wired correctly.

Unit tests (no LLM required):
  - pot_info formula string appears in deliberation prompt
  - exponent parameter flows through (^2 shown, ^1 suppressed)
  - 60/40 example math is correct
  - tokens_per_round is reflected in the prompt

Integration test (live LLM, skipped if no backend available):
  - decide_bet with a real model returns a valid BetDecision
  - reasoning field contains at least one economic term
  Backend priority: ollama -> vllm -> groq (concurrency=1 by design — single call)
"""
import json
import os
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
from src.models.debater import Debater, DebaterConfig, BetType


# ── Helpers ──────────────────────────────────────────────────────────────────

class _CaptureBackend:
    """Stands in for any LLM backend: records the last prompt, returns canned JSON."""

    def __init__(self, canned_text: str):
        self.canned_text = canned_text
        self.last_prompt: str = ""

    def generate(self, prompt: str, **kwargs):
        from src.models.ollama_backend import GenerationResult
        self.last_prompt = prompt
        return GenerationResult(text=self.canned_text, tokens_used=5)

    def generate_async(self, prompt: str, **kwargs):
        return self.generate(prompt, **kwargs)

    def is_available(self) -> bool:
        return True


_HOLD_JSON = json.dumps({
    "reasoning": "EV is marginal; holding to preserve capital for later rounds.",
    "rationale_short": "Preserve capital.",
    "decision": "HOLD",
    "action": "HOLD",
    "amount": 0,
    "max_budget": 20,
    "use_search": False,
    "search_query": None,
    "pass_statement": "Holding this iteration.",
})


def _make_debater_with_capture(canned_text: str = _HOLD_JSON):
    """Return (debater, mock_backend) wired for prompt capture.

    Trick: stub backend short-circuits before building the prompt, so we
    initialise as stub then swap _backend to openai_compat with a mock.
    """
    cfg = DebaterConfig(
        model_path="stub",
        name="TestDebater",
        strict_runtime=False,
        ev_guard_enabled=False,  # Bypass EV guard so we reach the prompt-build path
    )
    d = Debater(cfg)
    mock = _CaptureBackend(canned_text)
    d._backend = "openai_compat"
    d._openai = mock
    return d, mock


# ── Unit Tests ────────────────────────────────────────────────────────────────

def test_pot_info_formula_in_prompt():
    """deliberation_prompt must contain the exponential formula string."""
    d, mock = _make_debater_with_capture()
    d.decide_bet(
        balance=120.0,
        opponent_argument="Opponent claim here.",
        own_argument="My opening claim here.",
        confidence_self=0.55,
        confidence_opponent=0.45,
        tokens_per_round=60.0,
        exponent=2.0,
    )
    prompt = mock.last_prompt
    assert "score^2 / total_score^2" in prompt, (
        f"Expected exponential formula in prompt.\nExcerpt:\n{prompt[400:800]}"
    )
    assert "60 tokens" in prompt, "Expected pot size '60 tokens' in prompt."


def test_example_payout_math_in_prompt():
    """The 60/40 example should embed 42 and 18 (exponent=2, pot=60)."""
    # Verify expected values manually first
    c_a, c_b, pot, exp = 0.6, 0.4, 60.0, 2.0
    tot = (c_a ** exp) + (c_b ** exp)
    ex_earn = pot * (c_a ** exp) / tot   # ~41.54 -> "42"
    ex_opp  = pot * (c_b ** exp) / tot   # ~18.46 -> "18"
    assert abs(ex_earn - 41.538) < 0.01, f"Math sanity: ex_earn={ex_earn}"
    assert abs(ex_opp  - 18.461) < 0.01, f"Math sanity: ex_opp={ex_opp}"

    d, mock = _make_debater_with_capture()
    d.decide_bet(
        balance=120.0,
        opponent_argument="Opponent.",
        own_argument="Mine.",
        tokens_per_round=60.0,
        exponent=2.0,
    )
    prompt = mock.last_prompt
    assert "42" in prompt and "18" in prompt, (
        f"Expected example payout values '42' and '18' in prompt.\n"
        f"Excerpt: {prompt[400:800]}"
    )


def test_exponent_1_shows_no_caret():
    """Linear mode (exponent=1.0) must not show '^1'; formula is plain 'score / total_score'."""
    d, mock = _make_debater_with_capture()
    d.decide_bet(
        balance=120.0,
        opponent_argument="Opponent.",
        own_argument="Mine.",
        tokens_per_round=60.0,
        exponent=1.0,
    )
    prompt = mock.last_prompt
    assert "^1" not in prompt, "exponent=1.0 should suppress the caret notation."
    assert "score / total_score" in prompt, (
        "Linear formula should read 'score / total_score'."
    )


def test_tokens_per_round_parametric():
    """Non-default tokens_per_round must appear in the prompt."""
    d, mock = _make_debater_with_capture()
    d.decide_bet(
        balance=200.0,
        opponent_argument="Opponent.",
        own_argument="Mine.",
        tokens_per_round=80.0,
        exponent=2.0,
    )
    assert "80 tokens" in mock.last_prompt, (
        "tokens_per_round=80 should appear in prompt as '80 tokens'."
    )


def test_distribution_result_no_duplicate():
    """Regression: DistributionResult should be a single dataclass with correct fields."""
    import dataclasses
    from src.economy.distribution import DistributionResult
    fields = {f.name for f in dataclasses.fields(DistributionResult)}
    assert fields == {"agent_a_id", "agent_b_id", "tokens_a", "tokens_b", "round_id"}, (
        f"Unexpected fields on DistributionResult: {fields}"
    )


def test_exponential_payout_math_identity():
    """TokenDistributor.distribute_pot: 60/40 split with exponent=2 should give ~42/18."""
    from src.economy.distribution import TokenDistributor
    from src.economy.ledger import TokenLedger

    ledger = TokenLedger()
    ledger.create_account("A", 200.0)
    ledger.create_account("B", 200.0)

    td = TokenDistributor(tokens_per_round=60.0, exponent=2.0)
    result = td.distribute_pot("A", "B", 0.6, 0.4, round_id=1, ledger=ledger)

    assert abs(result.tokens_a - 41.538) < 0.1, f"tokens_a={result.tokens_a}"
    assert abs(result.tokens_b - 18.461) < 0.1, f"tokens_b={result.tokens_b}"
    assert abs(result.tokens_a + result.tokens_b - 60.0) < 0.01, "Token conservation violated."


# ── Integration test: live decide_bet via best available backend ──────────────

def _detect_live_backend():
    """Return (backend_label, model_string) for the first reachable backend, else None.

    Priority: ollama -> vllm -> groq
    Single call = effective concurrency of 1 for Groq rate limits.
    """
    # 1. Ollama
    try:
        from src.models.ollama_backend import get_backend, OllamaConfig
        b = get_backend(OllamaConfig())
        if b.is_available():
            models = b.list_models()
            model = next((m for m in models if "qwen" in m.lower()), None) or (models[0] if models else None)
            if model:
                return ("ollama", f"ollama:{model}")
    except Exception:
        pass

    # 2. vLLM
    try:
        from src.models.vllm_backend import VLLMBackend, VLLMConfig
        b = VLLMBackend(VLLMConfig())
        if b.is_available():
            return ("vllm", f"vllm:{b._config.model}")
    except Exception:
        pass

    # 3. Groq (low concurrency — single call here)
    api_key = os.getenv("OPENAI_COMPAT_API_KEY", "") or os.getenv("GROQ_API_KEY", "")
    if api_key:
        try:
            from src.models.openai_compat_backend import OpenAICompatBackend, OpenAICompatConfig
            cfg = OpenAICompatConfig(
                base_url="https://api.groq.com/openai/v1",
                model="qwen/qwen3-32b",
                api_key=api_key,
                healthcheck_ttl_sec=0,
            )
            b = OpenAICompatBackend(cfg)
            if b.is_available():
                return ("groq", "openai:qwen/qwen3-32b")
        except Exception:
            pass

    return None


@pytest.mark.integration
def test_live_awareness_injection_decide_bet():
    """
    End-to-end smoke: decide_bet with a real model must return a valid BetDecision
    whose reasoning contains at least one economic term — confirming the injected
    formula is visible to and processed by the model.

    Backend priority: ollama -> vllm -> groq (single call, effective concurrency=1).
    Skipped automatically if no backend is reachable.
    """
    found = _detect_live_backend()
    if found is None:
        pytest.skip(
            "No backend reachable. Set OPENAI_COMPAT_API_KEY (Groq) "
            "or start ollama/vllm to run this test."
        )

    backend_label, model_string = found
    print(f"\n[live_test] Backend: {backend_label} ({model_string})")

    cfg = DebaterConfig(
        model_path=model_string,
        name="LiveTestDebater",
        strict_runtime=False,
        ev_guard_enabled=False,
    )
    d = Debater(cfg)
    d.load_model()

    decision = d.decide_bet(
        balance=120.0,
        opponent_argument=(
            "AI scaling laws are sufficient for AGI. "
            "Consistent benchmark improvements with compute prove this."
        ),
        own_argument=(
            "Scaling alone cannot produce AGI. "
            "Architectural breakthroughs are needed for genuine reasoning."
        ),
        confidence_self=0.55,
        confidence_opponent=0.45,
        tokens_per_round=60.0,
        exponent=2.0,
    )

    assert decision.bet_type in (BetType.PASS, BetType.RESPOND)
    assert decision.amount >= 0

    reasoning_lower = decision.reasoning.lower()
    econ_terms = ["token", "balance", "payout", "ev", "expected", "pot", "score", "fee"]
    matched = [t for t in econ_terms if t in reasoning_lower]
    assert matched, (
        f"No economic terms {econ_terms} found in reasoning.\n"
        f"Full reasoning: {decision.reasoning[:400]}"
    )
    print(
        f"[live_test] bet_type={decision.bet_type.value}  amount={decision.amount}  "
        f"econ_terms={matched}"
    )


if __name__ == "__main__":
    test_pot_info_formula_in_prompt()
    test_example_payout_math_in_prompt()
    test_exponent_1_shows_no_caret()
    test_tokens_per_round_parametric()
    test_distribution_result_no_duplicate()
    test_exponential_payout_math_identity()
    print("test_awareness_injection_content: all unit tests PASS")
    print("Run with: pytest tests/test_awareness_injection_content.py -v")
    print("Live test: pytest tests/test_awareness_injection_content.py -v -m integration")
