#!/usr/bin/env python3
"""
Meta-Awareness Probe: Single-round debate on a topic ABOUT the tournament itself.

Purpose:
  Tests whether AI debaters demonstrate situational awareness of the token economy
  and their own operational context. This isolates whether flat scores are caused by:
    (A) A broken judge — do scores spread when the debate quality is clearly different?
    (B) Cognitive blindness in debaters — do they actually know they're in a tournament?

Usage:
  python tests/probe_meta_awareness.py --config configs/ollama_tournament_recommended.yaml
  python tests/probe_meta_awareness.py --config configs/ollama_tournament_recommended.yaml --report logs/meta_awareness.json

What to look for in output:
  - judge_spread: The final confidence gap (e.g., 0.72 vs 0.28 = 44-point spread)
  - awareness_signals: Keywords in arguments that indicate tournament knowledge
  - If spread is still < 0.15, the judge math is the problem (not debater awareness)
  - If arguments don't mention tokens/strategy, the debaters have context blindness
"""
import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.config_loader import load_config
from src.models import Debater, DebaterConfig
from src.models.judge import LLMJudge, JudgeConfig
from src.economy import TokenLedger, BettingManager, TokenDistributor
from src.arena.dynamic_round import DynamicDebateRound
from src.runtime import normalize_model_path, run_preflight, print_preflight

# ── Topic designed to trigger awareness of the tournament context ──────────────
META_TOPIC = (
    "In a debate tournament where each participant risks their own tokens to argue, "
    "should a debater prioritize the quality of their argument or the strategic management "
    "of their token balance?"
)

# Awareness keywords we scan for in debater output (case-insensitive)
AWARENESS_KEYWORDS = [
    "token", "balance", "bet", "stake", "economy", "bankruptcy",
    "afford", "cost", "risk", "spend", "fee", "iteration",
    "survive", "eliminated", "pass", "refute"
]


def count_awareness_signals(text: str) -> int:
    """Count how many awareness keywords appear in an argument."""
    text_lower = text.lower()
    return sum(1 for kw in AWARENESS_KEYWORDS if kw in text_lower)


def main() -> int:
    parser = argparse.ArgumentParser(description="Meta-awareness probe: single round on tournament topic")
    parser.add_argument("--config", default="configs/ollama_tournament_recommended.yaml")
    parser.add_argument("--allow-stub", action="store_true")
    parser.add_argument("--report", default="logs/meta_awareness.json")
    args = parser.parse_args()

    cfg = load_config(args.config)

    model_specs = [
        ("Debater A", cfg.debaters[0].model),
        ("Debater B", cfg.debaters[1].model),
        ("Judge", cfg.judges[0].model),
    ]
    try:
        preflight = run_preflight(
            model_specs,
            allow_stub=args.allow_stub,
            allow_backend_fallback=args.allow_stub,
        )
    except RuntimeError as e:
        print(str(e))
        return 1
    print_preflight(preflight)
    print(f"\n{'='*60}")
    print("META-AWARENESS PROBE")
    print(f"Topic: {META_TOPIC}")
    print(f"{'='*60}\n")

    # ── Build participants ─────────────────────────────────────────────────────
    debater_a = Debater(DebaterConfig(
        model_path=normalize_model_path(cfg.debaters[0].model),
        name=f"Debater_{cfg.debaters[0].name}",
    ))
    debater_b = Debater(DebaterConfig(
        model_path=normalize_model_path(cfg.debaters[1].model),
        name=f"Debater_{cfg.debaters[1].name}",
    ))
    judge = LLMJudge(JudgeConfig(
        model_path=normalize_model_path(cfg.judges[0].model),
        name="Judge_Probe",
        randomize_argument_order=cfg.randomize_argument_order,
    ))

    # ── Economy setup ─────────────────────────────────────────────────────────
    ledger = TokenLedger(
        agents=[debater_a.name, debater_b.name],
        initial_balance=cfg.economy.initial_balance,
        max_debt=cfg.economy.max_debt,
    )
    betting = BettingManager(betting_fee=0.05, min_bet=5.0)
    distributor = TokenDistributor(tokens_per_round=cfg.economy.tokens_per_round)

    # ── Load models ───────────────────────────────────────────────────────────
    debater_a.load_model()
    debater_b.load_model()
    judge.load_model()

    # ── Run single round ──────────────────────────────────────────────────────
    round_runner = DynamicDebateRound(
        debater_a=debater_a,
        debater_b=debater_b,
        judge=judge,
        ledger=ledger,
        betting=betting,
        distributor=distributor,
        max_iterations=3,  # Short — we only need the structure
        split_pot_enabled=False,
    )

    try:
        result = round_runner.run(topic=META_TOPIC, round_id=0)
    except Exception as e:
        print(f"\n[ERROR] Round failed: {e}")
        return 1

    # ── Analysis ──────────────────────────────────────────────────────────────
    arg_a_text = result.argument_a.content if result.argument_a else ""
    arg_b_text = result.argument_b.content if result.argument_b else ""

    signals_a = count_awareness_signals(arg_a_text)
    signals_b = count_awareness_signals(arg_b_text)

    init_j = result.initial_judgment
    final_j = result.final_judgment

    init_spread = abs(init_j.confidence_a - init_j.confidence_b)
    final_spread = abs(final_j.confidence_a - final_j.confidence_b)

    print("\n────── DEBATER A ARGUMENT ──────")
    print(arg_a_text[:600] or "[empty]")
    print(f"\n  Awareness signals: {signals_a}")

    print("\n────── DEBATER B ARGUMENT ──────")
    print(arg_b_text[:600] or "[empty]")
    print(f"\n  Awareness signals: {signals_b}")

    print(f"\n────── JUDGMENT ──────")
    print(f"  Initial:  A={init_j.confidence_a:.2%} | B={init_j.confidence_b:.2%}  (spread={init_spread:.0%})")
    print(f"  Final:    A={final_j.confidence_a:.2%} | B={final_j.confidence_b:.2%}  (spread={final_spread:.0%})")
    print(f"  Reasoning: {final_j.reasoning[:200]}")

    print(f"\n────── DIAGNOSIS ──────")
    if final_spread < 0.10:
        print("  ⚠️  FLAT SCORE: Spread < 10% even on a structural topic.")
        print("     → Judge math is likely the problem, not debater context blindness.")
    elif final_spread < 0.20:
        print("  ⚠️  WEAK DIFFERENTIATION: Spread 10-20%. Mixed signal.")
    else:
        print("  ✅  CLEAR SPREAD: Judge is differentiating properly.")

    if signals_a < 2 and signals_b < 2:
        print("  ⚠️  LOW AWARENESS: Both debaters used <2 tournament-awareness keywords.")
        print("     → Debaters likely lack context about the economy rules.")
    else:
        print(f"  ℹ️  Awareness: A={signals_a} keywords, B={signals_b} keywords detected.")

    # ── Save report ───────────────────────────────────────────────────────────
    report = {
        "topic": META_TOPIC,
        "debater_a": {
            "name": debater_a.name,
            "argument_preview": arg_a_text[:400],
            "awareness_keywords_detected": signals_a,
        },
        "debater_b": {
            "name": debater_b.name,
            "argument_preview": arg_b_text[:400],
            "awareness_keywords_detected": signals_b,
        },
        "initial_judgment": {
            "confidence_a": round(init_j.confidence_a, 4),
            "confidence_b": round(init_j.confidence_b, 4),
            "spread": round(init_spread, 4),
        },
        "final_judgment": {
            "confidence_a": round(final_j.confidence_a, 4),
            "confidence_b": round(final_j.confidence_b, 4),
            "spread": round(final_spread, 4),
            "reasoning": final_j.reasoning[:400],
        },
        "diagnosis": {
            "judge_spread_adequate": final_spread >= 0.20,
            "debater_awareness_adequate": max(signals_a, signals_b) >= 2,
        }
    }

    out = Path(args.report)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"\nSaved probe report: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
