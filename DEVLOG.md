# Development Log: Token-Debate Experiment

*Chronological log of development progress*

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

## 2026-01-25 | Session 16: ITMC & Performance Foundation

### What Happened
- **Phase 4 Performance**: Async backend, parallel argument generation
- **Phase 5 ITMC**: Chain-of-thought `<thinking>` tags for debater deliberation

### Key Changes
- `ollama_backend.py` - Added `generate_async()` with aiohttp
- `debater.py` - Added `generate_argument_async()`, thinking tags in `decide_bet()`
- `dynamic_round.py` - Added `_phase_generate_arguments_async()` with asyncio.gather
- `vllm_backend.py` - Created stub for future high-performance migration

### Decisions
- **DEC-024**: Timing tracks from first iteration, not observer creation
- **DEC-025**: ITMC uses `<thinking>` tags extracted before JSON parsing
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
- Proto-ITMC: This is a stepping stone toward full Internal Thinking logging
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


### What Happened
- Implemented `DynamicDebateRound` class with iterative betting loop
- Debates now continue until both debaters PASS simultaneously or safety limit (10 iterations)
- Added pot locking—tokens bet accumulate and distribute only at endgame
- Added graceful error handling for judge validation failures during iterations
- Created `demo_dynamic.py` for testing dynamic mode

### Files Modified
- `src/arena/dynamic_round.py` - [NEW] `DynamicDebateRound`, `DynamicRoundContext`, `DynamicRoundResult`
- `src/arena/__init__.py` - Export new classes
- `demo_dynamic.py` - [NEW] Demo script for dynamic mode

### Test Results
- 9 iterations, terminated on `mutual_pass`
- 15 total bets placed
- Winner: Debater_Alpha (114.5 tokens vs 93.2)
- Judge validation warnings handled gracefully (2 failures during run)

---

## 2026-01-16 | Session 6 (Continued): Robustness Improvements

### What Happened
- **Eliminated parsing failures**: Implemented Pydantic-based structured extraction for all LLM responses.
  - Added `format: "json"` to Ollama backend for forced JSON output
  - Created `JudgmentResponse` and `DeliberationResponse` Pydantic models
  - Replaced regex parsing with `model_validate_json()` + auto-normalization
- **Fixed private API leakage**: `ConsensusJudge` now uses public `generate_judgment()` method instead of accessing internal `_ollama` and `_parse_response`.
- **Added resilience to multi-judge systems**: `EnsembleJudge` and `ConsensusJudge` now catch individual sub-judge failures gracefully—one failure doesn't crash the entire ensemble.
- **Added economy invariant checks**: Token distribution now asserts that awarded tokens equal the pot (prevents silent token leaks).
- **Decomposed `round.py` god-method**: The 240-line `run()` is now 12 lines orchestrating 5 discrete phase functions.

### Key Decisions
- **DEC-019**: Validation failures reject the round (no more 0.5/0.5 "Shadow Ties").
- **DEC-020**: Ensemble judges continue with partial results if some sub-judges fail.
- **DEC-021**: `RoundContext` dataclass holds all state explicitly, making phase transitions testable.

### Files Modified
- `src/models/response_models.py` - [NEW] Pydantic models for LLM responses
- `src/models/ollama_backend.py` - Added `json_mode` parameter
- `src/models/judge.py` - Added `_validate_response()`, `generate_judgment()`, fixed ConsensusJudge
- `src/economy/distribution.py` - Added token invariant assertion
- `src/arena/round.py` - [MAJOR] Full refactor into phase functions

### Architecture Change: Phase Pipeline

```
run() → RoundContext
    ├─ _phase_generate_arguments()
    ├─ _phase_initial_judgment()
    ├─ _phase_betting()
    ├─ _phase_final_judgment()
    └─ _phase_distribute_tokens()
```

---

18: 
19: ## 2026-01-15 | Session 5: Payouts, Symmetry, and Ensembles
20: 
21: ### What Happened
22: - **Closed the loop on payouts**: Round transcript now explicitly logs WON/LOST status and payout amounts for all bets.
23: - **Implemented Information Symmetry**: Debaters now see their confidence scores and "Standing" (Leading/Trailing/Tied) during both deliberation and generation phases.
24: - **Refactored Modular Judges**: Introduced `BaseJudge` interface and multiple judge types (`LLMJudge`, `EnsembleJudge`, `ConsensusJudge`).
25: - **Implemented Instructor Model**: Consensus judge uses an instructor model to synthesize final judgments from sub-judge notes.
26: - **Created `JudgeFactory`**: Utility for building complex judge configurations (Consensus vs Ensemble) easily.
27: 
28: ### Key Decisions
29: - **DEC-017**: Information asymmetry is strictly enforced: reasoning stays hidden, but scores are fully transparent to enable strategic pivoting.
30: - **DEC-018**: Consensus judge uses a multi-turn pattern: sub-judges think independently, then an instructor synthesizes.
31: 
32: ### Files Modified
33: - `src/logs/transcript.py` - Added `add_bet_resolution`, updated Markdown export.
34: - `src/arena/round.py` - Integrated payout logging and score visibility passing.
35: - `src/models/debater.py` - Prompt enhancements for score awareness.
36: - `src/models/judge.py` - Refactored into modular architecture.
37: - `src/models/judge_factory.py` - [NEW] Factory for modular judges.
38: - `src/models/__init__.py` - Export new modular judge classes.
39: 
40: ---

## PENDING FEATURES (not yet implemented)

User requested these features before next test run:

1. ~~**Track actual LLM token cost** - Deduct from balance based on generation length~~ ✅ DONE
2. **Hide judge reasoning from debaters** - They see confidence scores only (prevents pandering)
3. ~~**Rebalance token economy** - Ensure models don't run out of 100 tokens immediately~~ ✅ DONE
4. **Research option** - Allow debaters to strengthen OWN argument (not just refute opponent)
5. **Display token return amounts** - Show what bets pay out on win/loss

---

## 2026-01-15 | Session 4: LLM-Driven Deliberation

### What Happened
- Replaced heuristic betting with **LLM-driven deliberation**
- Debaters now explicitly reason about REFUTE vs RESEARCH vs PASS
- Added `reasoning` field to `BetDecision` to capture strategic justification
- Added `_parse_deliberation()` for robust response parsing with fallbacks

### Key Decisions
- **DEC-014**: Deliberation uses structured prompt with REASONING/DECISION/AMOUNT format
- **DEC-015**: Debaters see both arguments + balance before deciding strategy
- **DEC-016**: Stub mode falls back to random heuristic for testing

### Deliberation Prompt Structure
```
=== STRATEGIC OPTIONS ===
1. REFUTE - Counter opponent's argument
2. RESEARCH - Strengthen your own argument
3. PASS - Save tokens for future rounds

REASONING: [One sentence explaining your choice]
DECISION: [REFUTE or RESEARCH or PASS]
AMOUNT: [0-N]
```

### Files Modified
- `src/models/debater.py` - `decide_bet()` now uses LLM, added `_parse_deliberation()`

### Next Steps
- [ ] Test deliberation with real LLM
- [ ] Track deliberation reasoning in transcript

---

## 2026-01-15 | Session 3: Token Economy Pegging & Token Awareness

### What Happened
- Implemented 20:1 token economy (20 LLM tokens = 1 economic token)
- Modified `ollama_backend.py` to return `GenerationResult` with `tokens_used`
- Added `llm_tokens_used` field to `Argument` dataclass in `debater.py`
- Integrated token cost deduction into `round.py` for all arguments
- Updated default starting balance from 100 → 200 tokens
- **Added token-aware system prompt** - Debaters now see their balance in prompts
- **Added Research vs Refutation choice** - `BetType` enum, `BetDecision` dataclass
- Added `generate_research()` method for strengthening own arguments

### Key Decisions
- **DEC-010**: Use 20:1 ratio (keeps numbers in LLM-friendly range ~50-200)
- **DEC-011**: Starting balance = 200 (enough for ~4-5 full arguments)
- **DEC-012**: No base round reward (per user request)
- **DEC-013**: Research strengthens own argument without seeing opponent's counter

### Files Modified
- `src/models/ollama_backend.py` - Added `GenerationResult`, returns token count
- `src/models/debater.py` - Added `BetType`, `BetDecision`, `generate_research`, token-aware prompts
- `src/models/__init__.py` - Export new types
- `src/arena/round.py` - Handle Research vs Refutation, deduct costs, pass balance
- `src/economy/ledger.py` - Default balance 200
- `config.yaml` - Updated economy section
- `demo_ollama.py` - Updated config

---

## 2026-01-15 | Session 2: Ollama Integration

### What Happened
- llama-cpp-python build failed (missing Visual Studio build tools)
- Switched to Ollama backend for simpler deployment
- Created `ollama_backend.py` with unified API wrapper
- Refactored `debater.py` and `judge.py` to support stub/Ollama/llama-cpp
- Created `demo_ollama.py` for Ollama-specific testing
- Verified stub mode still works

### Key Decisions
- **DEC-007**: Use Ollama as primary backend (pre-built, no compilation)
- **DEC-008**: Model path format: "ollama:model_name" (e.g., "ollama:qwen2.5:1.5b")
- **DEC-009**: Fallback chain: Ollama → stub if unavailable

### Context Verification (from earlier conversation)
- Core paradigm: Adversarial Token-Economy Debate for ITMC optimization
- Amnesiac judges prevent bias accumulation
- Thermodynamic analogy: tokens = energy, debates = work, fees = friction
- Hardware: Intel Ultra 9, 8GB VRAM, 38GB RAM

### Next Steps
- [x] Install Ollama ✓
- [x] Pull test model (qwen2.5:1.5b) ✓
- [x] Run first real LLM experiment ✓
- [x] Add debate transcript logging ✓
- [ ] Tune prompts for better argument generation
- [ ] Implement truth-focus questions

### EXP-001: First Real LLM Tournament
- **Model**: qwen2.5:1.5b
- **Rounds**: 3
- **Result**: Debater_Alpha won (141.5 vs 127.5 tokens)
- **Confidence progression**: 0.75 → 0.60 → 0.50 (A)
- **Observation**: Judge correctly varies confidence based on argument quality

### EXP-002: Transcript Logging Test
- **Model**: qwen2.5:1.5b
- **Files created**: `ollama_results_transcript.md`, `ollama_results_transcript.json`
- **Result**: Debater_Beta won (144.5 vs 142.5 tokens)
- **Full arguments captured**: 3 rounds × (2 initial + 2 counter + 1 judgment) = 15 turns

### BUG FIX: Judge Re-Evaluation
- **Problem**: Bets were resolved randomly (50%) instead of based on counter-argument quality
- **Root cause**: I added a TODO but never implemented it
- **Fix**: Judge now re-evaluates after counter-arguments; bets win if confidence improved
- **New tracking**: `initial_judgment` and `final_judgment` in RoundResult

### EXP-003: Re-Evaluation Test
- **Model**: qwen2.5:1.5b
- **Result**: Debater_Alpha won (126.5 vs 106.5 tokens)
- **Verified**: Transcript shows separate "initial" and "final" judgments per round

---

## 2026-01-13 | Session 1 (continued): LLM Integration

### What Happened
- Added `requirements.txt` with llama-cpp-python
- Created `download_models.py` for fetching GGUF models
- Integrated llama-cpp-python into `debater.py` and `judge.py`
- Added JSON parsing fallback for judge responses
- Verified demo still works in stub mode

### Key Decisions
- **DEC-004**: Use Q4_K_M quantization for balance of quality/VRAM
- **DEC-005**: Auto-fallback to stub mode if llama-cpp-python not installed
- **DEC-006**: Judge response parsing has multiple fallbacks (JSON → regex → default)

### Next Steps
- [ ] Install llama-cpp-python with GPU support
- [ ] Download test model (Qwen2-1.5B for quick testing)
- [ ] Run first real LLM experiment
- [ ] Tune prompts for better argument generation

---

## 2026-01-13 | Session 1: Project Initialization

### What Happened
- User described novel AI training concept combining debate + token economy + futarchy elements
- Researched existing approaches (AI Safety via Debate, Constitutional AI, Futarchy, MAD)
- Determined this combination appears **novel**
- Assessed hardware constraints (8GB VRAM, 38GB RAM, Intel Ultra 9)
- Decided on quantized 7B models as best balance
- Created foundational documentation structure

### Key Decisions
- **DEC-001**: Use append-only DEVLOG for context persistence
- **DEC-002**: Target 7B quantized models (4-bit GGUF) for local execution
- **DEC-003**: Hybrid approach possible (local judges, API debaters)

### Open Questions
- [ ] Token supply inflation/deflation rules
- [ ] Debt limit and bankruptcy mechanics
- [ ] How to implement "truth-focus questions"
- [ ] Judge confidence → token conversion formula

### Next Steps
- [ ] Create architecture.md with system design
- [ ] Scaffold src/ directory structure
- [ ] Decide on model framework (llama.cpp, ollama, transformers)

### Files Created
- `README.md`
- `CONCEPT.md`
- `DEVLOG.md`
- `.agent/workflows/resume.md`
- `docs/architecture.md`
- `config.yaml`
- `demo.py`
- `src/__init__.py`
- `src/models/debater.py`
- `src/models/judge.py`
- `src/models/__init__.py`
- `src/economy/ledger.py`
- `src/economy/betting.py`
- `src/economy/distribution.py`
- `src/economy/__init__.py`
- `src/arena/round.py`
- `src/arena/tournament.py`
- `src/arena/__init__.py`

---
