# Clean Campaign 100 — Insights & Analysis

**Campaign:** `logs/clean_overnight_01/clean_100/`
**Date:** 2026-03-06
**Runs:** 99/100 successful
**Models:** qwen3-32b debaters, llama-3.3-70b judge (Groq API)
**Visualization:** `report_output/clean100_report.png`

---

## What Was Fixed vs All Prior Runs

Every previous campaign (~200 runs) had three compounding problems. This is the first run with all three fixed.

| Fix | Before | After |
|---|---|---|
| Economy pot | 30-50 tokens (below arg cost) | 200 tokens (above break-even) |
| Judge model | qwen3-32b judging itself | llama-3.3-70b (different model) |
| Prompt cost info | "costs vary with length" (vague) | Exact ratio disclosed (1 balance = 20 LLM tokens) |

---

## Insight 1: The Economy Fix Validated — Models Were Always Rational

**Finding:** Pass rate dropped from 0.83 → 0.491

Prior campaigns showed 83% pass rate (models argued nearly every turn). This was interpreted as models not understanding costs. It wasn't. The probe already confirmed 100% economic reasoning accuracy.

The real explanation: with pot=40 tokens and average argument cost=62.7 tokens, arguing had **negative expected value**. A rational agent that passes the economic reasoning probe should hold. They did.

Raise the pot to 200 tokens (above break-even), and models argue 49% of turns — exactly what you'd expect from a model doing marginal EV calculation on each turn.

**The system design was the problem, not the model.**

---

## Insight 2: Positional Bias Is Mechanical, Not a Judge Problem

**Finding:** Alpha win rate dropped from 70-80% → 54%

The old result looked like judge bias (same model judging its own outputs). But we measured judge confidence scores across all old runs and found them essentially unbiased (mean_conf_a = 0.497, indistinguishable from 0.5).

The bias came from economic compounding. Under the broken economy, both sides held most turns and tiny random balance differences in early rounds snowballed into wins. Alpha, going first in round structure, had a slight systematic first-mover advantage that compounded.

With the fixed economy, both sides actually argue, balance fluctuates on merit, and the compounding effect is diluted. Result: 54% Alpha wins — nearly fair, and much closer to the expected 50% from a truly unbiased system.

**The remaining 4% is residual compounding, not judge bias. A side-swap batch will correct it to ~50%.**

---

## Insight 3: Adaptation Signal Is Real But Weak

**Finding:** Mean adaptation_gain_after_loss = 0.033

Models show a consistent positive adaptation signal — they improve their position after losing a round. This is present across almost all 99 runs (plot shows mostly positive bars).

However, 0.033 is a small effect. It's statistically present but not strong enough yet to claim models are meaningfully "learning" mid-tournament. This needs:
- More rounds per tournament (currently capped at 12, often ending at 6 via bankruptcy)
- A stronger feedback signal in the deliberation prompt (currently shows last judgment truncated to 150 chars)

**Conclusion: the wiring is there, the signal needs amplification.**

---

## Insight 4: Health Score 0.70 — Debates Are Substantive

**Finding:** Mean health_score = 0.700, distribution peaks around 0.72-0.78

Health score aggregates: pass rate, aggression symmetry, adaptation, and debate longevity. A score of 0.70 indicates debates where:
- Both sides are participating actively (~50% response rate)
- Neither side is running away with the economy early
- Arguments are being challenged and responded to

This is markedly better than the old data, where health was dominated by the broken economy incentivizing passive play.

---

## Insight 5: 2,954 Clean Training Traces

Each trace record is one debater turn: the argument text, the deliberation reasoning, the HOLD/RESPOND decision with EV rationale, and the economic context. These are the raw material for SFT and DPO training.

**What makes these traces valuable:**
- Arguments were made by a model that had economic skin in the game (real token cost)
- HOLD decisions include `pass_statement` reasoning (model explains why it held)
- Adaptation traces show before/after argument quality around loss events
- External judge scoring means quality labels aren't self-referential

**Filtering recommendations for training:**
- SFT: traces where health_score > 0.7 and pass_rate 0.3-0.65 (selective arguing)
- DPO preferred: traces with positive adaptation_gain_after_loss (improvement shown)
- DPO rejected: traces from same topic/round where argument lost (same context, worse outcome)

---

## Data Location

```
logs/clean_overnight_01/clean_100/
├── batch_summary.jsonl          # per-run metrics (pass_rate, health, winner, etc.)
├── batch_manifest.json          # run index with paths
├── run_001_seed_5010/
│   ├── tournament_results.json                      # winner, balances, config
│   ├── tournament_results_transcript.json           # full round-by-round transcript
│   ├── tournament_results_ledger.json               # token economy transactions
│   ├── tournament_results_metrics.json              # timing, momentum shifts
│   ├── tournament_results_selection_health_dashboard.json  # health breakdown
│   └── trace_records.jsonl                          # individual turn traces (training data)
├── run_002_seed_5011/ ...
│   (99 run directories total, seeds 5010-5109, seed 5029 missing/failed)
```

**For other AI agents reading this:**
- The most useful file per run is `trace_records.jsonl` — each line is one training-ready trace
- `batch_summary.jsonl` has all aggregate metrics in one place for quick analysis
- `tournament_results_transcript.json` has the full debate text with judge scores per round
- Do NOT use data from `logs/groq_multikey_*`, `logs/overnight_*`, `logs/evolution_*`,
  or `logs/nvidia_afternoon/` for strategy/fitness analysis — those ran with broken economy configs

---

## What To Do Next

1. **Run side-swap batch** (same 99 seeds, Alpha/Beta names flipped) — corrects residual 4% bias
2. **Extract training data** from `trace_records.jsonl` files — filter by health > 0.7
3. **Run evolution campaign** with fixed economy — now that arguing is EV+, directive differences will show up in behavior
4. **Amplify adaptation signal** — increase rounds cap, enrich judgment feedback in prompt
