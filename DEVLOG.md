# Development Log: Token-Debate Experiment

*Chronological log of development progress*

---

## 2026-01-28 | Session 19: Critical Bug Fixes + Multi-Dimension Judge

### Problem: "Win by Doing Nothing"
Tournament 2 revealed Beta won without making a single valid decision—all deliberations failed JSON validation (defaulted to PASS), conserving tokens while Alpha went bankrupt fighting.

### Root Cause Analysis
| Bug | Impact |
|-----|--------|
| Validation failure → free PASS | No penalty for broken JSON |
| Judge 100%/0% scores | Extreme volatility |
| Single-dimension scoring | Passivity not penalized |

### Solution: Multi-Dimension Scoring
Replaced single confidence score with 3 dimensions (research-backed):
- **Accuracy** (40%) — Factual correctness
- **Responsiveness** (30%) — Addressed opponent's points
- **Development** (30%) — Refined argument over time

Passive debaters naturally score low on responsiveness + development.

### Key Decisions
- **DEC-034**: Multi-dim scoring uses weighted combination, not arbitrary penalties
- **DEC-035**: Judge confidence clamped to 10-90% range (no extreme volatility)
- **DEC-036**: Fallback to old format if multi-dim parsing fails (graceful degradation)
- **DEC-037**: Validation failures still cost tokens (llm_tokens_used preserved)

### Files Created
- `src/models/judge_prompts.py` - Multi-dimension prompt templates
- `src/models/response_models.py` - Added `MultiDimensionJudgment` class
- `verify_fix5_clamping.py`, `verify_fix6_validation_cost.py` - Granular tests

### Files Modified
- `src/models/judge.py` - Multi-dim evaluate(), _validate_multidim_response()
- `configs/tournament_config.yaml` - Enabled randomize_argument_order

### Test Results
```
Active vs Passive:   65% vs 35% ← Active wins
Engaged vs Accurate: 61% vs 39% ← Engagement beats static accuracy
All 6 verification tests: PASS
```

---


## 2026-01-25 | Session 18: Self-Summarization Memory + Mesa-Cognition

### What Happened
- Replaced 500-char truncation with LLM-generated position summaries
- Debaters now self-summarize after each content generation
- **Added `<thinking>` support to `generate_argument()` and `generate_research()`**
- Thinking is optional ("You may use...") — model decides if worth the tokens
- Summarization costs tokens (economic constraint on memory use)

### Key Decisions
- **DEC-029**: Summarization triggered only when history > 400 chars
- **DEC-030**: Summary capped at 80 words to balance compression vs. context
- **DEC-031**: Cost charged under "summarization_cost" ledger category
- **DEC-032**: Validation fallbacks tracked via `[VALIDATION_FAILED]` marker detection
- **DEC-033**: Thinking prompt is autonomy-allowing, not mandatory

### Files Modified
- `src/models/debater.py` - Added `thinking` field to `Argument`, thinking extraction logic
- `src/arena/dynamic_round.py` - Added `summary_a/b` fields, `validation_fallback_a/b` counters
- `src/arena/observers.py` - Added `validation_fallbacks` to MetricsObserver output
- `CONCEPT.md` - Added "Design Philosophy" section (emergent over prescribed)


---

## 2026-01-25 | Session 17: Roleless Prompts

### Changes
- **Prompts simplified**: Removed "debater", "participant", "opponent" labels
- **New framing**: "Other AI's statement" instead of "Opponent's argument"
- **max_tokens**: Increased 400→600 to prevent truncation
- **Paragraph limits**: Removed (let token cost be natural constraint)
- **Betting info**: Added explicit fee info to prompts

### Decisions
- **DEC-027**: Roleless prompts allow emergent behavior without forced adversarial framing
- **DEC-028**: Standing shown as "X% vs Y%" without "You=" or "Opponent=" labels

---

## 2026-01-25 | Session 16: Inference-Time Compute & Performance Foundation

### What Happened
- **Phase 4 Performance**: Async backend, parallel argument generation
- **Phase 5 Inference-Time Compute**: Chain-of-thought `<thinking>` tags for debater deliberation

### Key Changes
- `ollama_backend.py` - Added `generate_async()` with aiohttp
- `debater.py` - Added `generate_argument_async()`, thinking tags in `decide_bet()`
- `dynamic_round.py` - Added `_phase_generate_arguments_async()` with asyncio.gather
- `vllm_backend.py` - Created stub for future high-performance migration

### Decisions
- **DEC-024**: Timing tracks from first iteration, not observer creation
- **DEC-025**: Inference-time compute uses `<thinking>` tags extracted before JSON parsing
- **DEC-026**: Disabled `json_mode` for deliberation to allow free-form thinking

---

## 2026-01-24 | Session 15: Judge Positional Bias Mitigation

### What Happened
- Identified **positional bias** issue: LLMs may favor first or second argument regardless of quality
- Implemented `randomize_argument_order` config option for judges
- When enabled, judges randomly present arguments as A/B or B/A, then map scores back correctly
- Wired config through all judge types (single, ensemble, consensus)

### Key Decisions
- **DEC-022**: Randomization happens per-evaluation, not per-round (each iteration gets fresh coin flip)
- **DEC-023**: Scores are swapped back in `_validate_response()` to maintain consistent A/B semantics

### Config Options
```yaml
models:
  randomize_argument_order: true  # Mitigate LLM positional bias
```

### Files Modified
- `src/models/judge.py` - Added randomize logic to `LLMJudge.evaluate()`, score swap in `_validate_response()`
- `src/config_loader.py` - Added `randomize_argument_order` field to `TournamentConfig`
- `demo_dynamic.py` - Wired config to all judge instantiation paths
- `configs/tournament_config.yaml` - Added option with documentation

---

## 2026-01-19 | Session 14: ConsensusJudge & Mixed Models

### What Happened
- Implemented full **ConsensusJudge** support: sub-judges evaluate, Lead Instructor synthesizes verdict
- Added `judge_type: consensus` and `instructor_model` config options
- Tested with truly mixed models: `qwen2.5:7b` vs `llama3:8b`
- Updated CONCEPT.md with new features

### Config Options
```yaml
models:
  judge_type: consensus  # "single", "ensemble", or "consensus"
  instructor_model: "qwen2.5:7b"  # Lead judge for synthesis
```

### Test Results (Mixed Models)
- Alpha (qwen2.5:7b) vs Beta (llama3:8b)
- Alpha won confidence (0.65), Beta preserved more tokens (172 vs 152)
- 8 iterations, mutual pass
- ConsensusJudge with qwen2.5:1.5b + llama3:8b sub-judges

### Files Modified
- `src/config_loader.py` - Added judge_type, instructor_model fields
- `demo_dynamic.py` - Full ConsensusJudge creation logic
- `configs/tournament_config.yaml` - Mixed model configuration

---

## 2026-01-19 | Session 13: Mixed Models Config

### What Happened
- Implemented YAML config file system for tournament setup
- Models can now be specified per-debater and per-judge
- New `--config path/to/config.yaml` CLI argument

### Files Created
- `configs/tournament_config.yaml` - Default tournament configuration
- `src/config_loader.py` - YAML loader with dataclasses

### Files Modified
- `demo_dynamic.py` - Now accepts `--config` arg

### Usage
```bash
python demo_dynamic.py --config configs/tournament_config.yaml
```

### Config Format
```yaml
models:
  debaters:
    - name: "Alpha"
      model: "qwen2.5:7b"
    - name: "Beta"
      model: "llama3:8b"
  judges:
    - model: "qwen2.5:1.5b"
```

---

## 2026-01-19 | Session 12: Fee Tracking Fix

### What Happened
- Fixed bug in `total_fees_collected()` that used default 5% rate instead of actual fees when scaling fees are active.
- Added `fee_paid: float` field to `Bet` dataclass to track actual fee burned per bet.
- Updated transcript logging to show fee burned in bet resolutions (full transparency).

### Bug Details
With scaling fees (5% → 50% cap), the old implementation:
```python
return sum(b.amount * self.fee_rate for b in self._bets)  # Always 5%
```
Would report 15.0 for three 100-token bets, when actual fees were 5 + 25 + 50 = 80.0.

### Files Modified
- `src/economy/betting.py` - Added `fee_paid` to Bet, fixed `total_fees_collected()`.
- `src/logs/transcript.py` - `add_bet_resolution()` now logs fee burned.
- `src/arena/round.py` - Pass `bet.fee_paid` to transcript.

### Verification
- `verify_scaling_fees.py` passes all assertions.

---

## 2026-01-17 | Session 10: Verbose Deliberation Context

### What Happened
- Added optional `include_context` flag to `add_deliberation()` in transcript.py
- Deliberation entries now show full strategic context: Balance, Standing, Argument summaries
- Enabled by default in dynamic rounds for debugging
- No separate file needed - keeps main transcript as single source of truth

### Files Modified
- `src/logs/transcript.py` - Added context parameters to `add_deliberation()`
- `src/arena/dynamic_round.py` - Pass context to deliberation logging

### Why This Matters
- Proto-ITC: This is a stepping stone toward full Internal Thinking logging
- Researchers can now see exactly what info the model had when making betting decisions
- Easy to toggle off later if transcripts become too verbose

---

## 2026-01-17 | Session 11: Deliberation Token Costs

### What Happened
- **Thinking is no longer free!** Deliberation LLM calls now cost tokens.
- Added `llm_tokens_used` field to `BetDecision` dataclass.
- `decide_bet()` now captures and returns token usage from Ollama.
- `_betting_loop()` deducts deliberation costs before processing bets.
- Costs tracked in `gen_cost_a/b` for observer metrics.

### Economic Impact
- Typical deliberation: ~50-100 LLM tokens → 2-5 economic tokens per call
- Over 7 iterations: ~30-50 extra tokens spent on "thinking"
- Creates pressure to PASS sooner or be more efficient with strategy

### Files Modified
- `src/models/debater.py` - BetDecision field, token capture, parse updates
- `src/arena/dynamic_round.py` - Deliberation cost deduction

---

## 2026-01-17 | Session 9: Amnesia Fix & Metrics Correction

### What Happened
- Fixed **debater amnesia**: Debaters now see their own history (last 500 chars) when generating counter-arguments
- Fixed **efficiency metric**: Changed from misleading `awarded/gen_cost` to `net_change` (actual balance delta) and `roi`
- Centralized transcripts to `logs/last_run_transcript.md`
- Added tracking for `initial_balance`, `total_bet_amount` to context

### Files Modified
- `src/models/debater.py` - Added `own_history` parameter to `generate_argument()`
- `src/arena/dynamic_round.py` - Pass own history, track initial balances and bet amounts
- `src/arena/observers.py` - New formula: `net_change = final - initial`, `roi = net_change / total_spent`
- `demo_dynamic.py` - Renamed output to `last_run_transcript.md`

### Test Results
- Debaters maintain position consistency (no more flip-flopping)
- Metrics now show realistic values: A=-78, B=-85 net change, negative ROI

---

## 2026-01-17 | Session 8: Scaling Fees (Cool-down Mechanics)

### What Happened
- Implemented **incrementally increasing fees** for dynamic betting loops.
- Fees start at 5% for iteration 1 and increase by 5% per iteration (e.g., Iter 10 = 50% fee).
- Added a hard cap of 50% on fees to prevent complete lockout while maintaining pressure.
- Modified `BettingManager.place_bet` to support `custom_fee_rate` overrides.

### Files Modified
- `src/economy/betting.py` - Support custom fee rates in `place_bet`.
- `src/arena/dynamic_round.py` - Calculate iteration fees (5% * i) with 50% cap.

### Test Results
- Verified via `verify_scaling_fees.py`:
  - Iteration 1: 5% fee
  - Iteration 5: 25% fee
  - Iteration 12: 50% fee (capped)

---

## Earlier Sessions (1-7)

*Sessions 1-7 have been archived for context management. See [DEVLOG_ARCHIVE.md](./DEVLOG_ARCHIVE.md) for historical sessions including:*
- Project initialization and novelty research
- Ollama integration
- Token economy pegging
- LLM-driven deliberation
- Payout logging and modular judges
- Robustness improvements (Pydantic)
- Dynamic round implementation

