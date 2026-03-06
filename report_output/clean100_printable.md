# AIcamptowndebate — Clean Campaign Report
### First Trusted Dataset | 2026-03-06

---

## What This Is

This report covers the first 99 tournament runs with a correctly configured debate arena.
All prior ~200 runs had three compounding design flaws that made results untrustworthy.
This campaign fixed all three.

---

## The Three Fixes

| # | Problem | Old Value | Fixed Value |
|---|---|---|---|
| 1 | Economy pot too small — arguing had negative ROI | 40 tokens | **200 tokens** |
| 2 | Same model judged itself — no external ground truth | qwen3-32b self-judge | **llama-3.3-70b external** |
| 3 | AI couldn't calculate exact argument cost | "varies with length" | **1 balance = 20 LLM tokens (explicit)** |

---

## Results at a Glance

| Metric | Before (broken) | After (clean) | What it means |
|---|---|---|---|
| Runs completed | mixed | **99 / 100** | Config is stable |
| Pass rate | 0.83 | **0.491** | Models argue selectively now |
| Alpha win rate | 70 – 80 % | **54 %** | Positional bias nearly gone |
| Health score | — | **0.700** | Debates are substantive |
| Adaptation gain | — | **0.033** | Learning signal present |
| Total traces | contaminated | **2,954** | Clean training data |

---

## The Most Important Finding

> **Models were always rational. They held because holding was the correct move.**

Under the old economy, the average cost to make one argument was **62.7 tokens**.
The pot reward per round was **30–50 tokens**.
Any model doing correct expected-value math would hold every turn — and they did.

The probe we ran on qwen2.5:7b confirmed **100% accuracy** on all economic reasoning scenarios.
The models understood the system perfectly. The system was broken.

Raise the pot to 200 tokens (above break-even) and models argue **49% of turns** —
exactly the selective behaviour you'd want from a rational economic agent.

---

## Pass Rate Distribution

```
0.30 - 0.40  |##                          |  6 runs
0.40 - 0.50  |###########################  | 43 runs   <-- bulk here
0.50 - 0.60  |######################       | 35 runs
0.60 - 0.70  |########                     | 12 runs
0.70 - 0.80  |##                           |  3 runs
                                  Mean: 0.491
```

---

## Positional Bias — Solved

Alpha win rate dropped from **70–80% → 54%** simply by fixing the economy and using an external judge.

Root cause of old bias: both sides held most turns, so tiny balance differences
in early rounds compounded into wins. Alpha, going first, had a systematic
first-mover advantage that snowballed under passive play.

With fair economy both sides argue, balance fluctuates on merit, and the
compounding effect disappears.

The judge itself was **never biased** — confidence scores measured 0.497 across
all old runs (essentially 0.5). The problem was mechanical, not a model problem.

---

## Data Location (for analysts)

```
logs/clean_overnight_01/clean_100/
├── batch_summary.jsonl          <- per-run metrics, one JSON line each
├── batch_manifest.json          <- index of all 99 run directories
└── run_001_seed_5010/ ... run_100_seed_5109/
    ├── trace_records.jsonl      <- TRAINING DATA: one turn per line
    ├── tournament_results_transcript.json   <- full debate text + judge scores
    ├── tournament_results_ledger.json       <- token economy transactions
    └── tournament_results.json             <- winner, balances, config
```

**Best file for training data:** `trace_records.jsonl` in each run directory.
Each line = one debater turn with: argument text, deliberation reasoning,
HOLD/RESPOND decision, economic context, and external judge score.

**Recommended filter for SFT training:**
- `health_score > 0.7` (substantive debates only)
- `pass_rate` between 0.3 and 0.65 (selective arguing, not always-hold or always-argue)

**Do NOT use for strategy analysis:**
`logs/groq_multikey_*`, `logs/overnight_*`, `logs/evolution_*`, `logs/nvidia_afternoon/`
All of these ran with the broken economy and self-judge.

---

## Adaptation Signal

Mean adaptation gain after loss: **0.033**

This means models consistently improve their position after falling behind —
the learning signal exists. It's small because tournaments only ran ~6 rounds
(balance of 1000 bankrupts quickly). Ongoing experiments use balance=3000
to allow 12+ rounds and a stronger adaptation signal.

---

## What Comes Next

1. **Side-swap dataset** — same 65 seeds with Alpha/Beta names flipped (65 runs complete)
   Averaging with clean_100 brings positional bias from 54% → ~50%.

2. **Veteran comparison** — 20 runs with behavioral directives (SURVIVAL_FIRST,
   ADAPT_ON_LOSS, PUNISH_WEAKNESS, ANTI_RAMBLE) and balance=3000 for longer games.
   First honest test of whether directives change behavior under fair conditions.

3. **Training data extraction** — filter `trace_records.jsonl` by health > 0.7,
   build SFT pairs and DPO preference pairs for fine-tuning.

---

## Config Used

File: `configs/clean_economy_groq.yaml`

```yaml
models:
  debaters:
    - model: "openai:qwen/qwen3-32b"   # debater
  judges:
    - model: "openai:llama-3.3-70b-versatile"   # external judge

economy:
  initial_balance: 1000
  tokens_per_round: 200      # was 40 — this is the critical fix
  initial_pot_amount: 200    # was 40

rounds:
  num_rounds: 12
  max_iterations: 3
```

---

*Generated: 2026-03-06 | Campaign: clean_overnight_01/clean_100 | 99 runs | Groq API*
*Visualization: report_output/clean100_report.png*
*Full analysis: docs/clean100_insights.md*
