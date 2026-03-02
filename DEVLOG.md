## 2026-03-02 | Session 24: Balanced Roadmap Reset (70/20/10) + Execution Prep

### Why This Session
- We intentionally widened scope after a period of narrow benchmark plumbing focus.
- Goal: preserve scientific rigor while reopening high-upside exploration.

### Balanced Roadmap (12 Weeks)

#### 70% Core (Must-Win)
1. **Evidence Engine**
   - Standardize dual-lane scoring (`fixture_static` + `model_derived`) and claim packet outputs.
   - Add uplift confidence reporting for decision quality.
2. **Closed-Loop Economy Control**
   - Auto-tune fee/min-bet/token issuance to maintain target entropy + adaptation behavior bands.
3. **Population Arena**
   - Move from fixed A/B into multi-model Swiss/challenger scheduling.

#### 20% Adjacent (Near-Term Upside)
4. **Adversarial Robustness Track**
   - Add attack-style benchmark slices (injection/trap/framing) as promotion gates.
5. **Strategy Explainability Layer**
   - Produce compact turning-point artifacts (why decisions flipped, what changed confidence).

#### 10% Moonshot
6. **Parliament/Coalition Mode**
   - Prototype multi-agent coalition + minority-report governance dynamic.

### Worth-It Prioritization (Current Recommendation)
- **Highest ROI now:** Evidence Engine -> Closed-Loop Economy -> Population Arena.
- **Strong but second wave:** Robustness Track, then Explainability Layer.
- **Exploratory only:** Parliament mode (timeboxed spike, continue only if measurable new signal appears).

### Elegant Implementation Prep
1. Keep one canonical artifact contract (summary, provenance, uplift, invariants).
2. Add one feature flag per new lane to keep baseline reproducible.
3. Require seed-level reproducibility before enabling policy gates.
4. Add kill criteria per track (pause after two sprints with no measurable movement).

### Skill Command Guidance
- **Do not force skill commands by default** for core roadmap implementation; normal code/test workflow is fastest.
- Use **`playwright`** only when adding or validating real UI/dashboard flows.
- Use **`skill-creator`** once repeated workflows stabilize (recommended custom skill: benchmark-governance runbook).
- Use **`skill-installer`** only if a missing capability becomes a blocker.

---
## 2026-02-21 | Session 23: Research-Grade Runtime Guardrails, vLLM Integration, and Experiment Tooling

### What Happened
- Reconciled documentation and implementation drift across demos, configs, tests, and runtime behavior.
- Added strict experiment preflight checks to block invalid runs (backend unavailable, stub/fallback in strict mode).
- Added judge-variance gating and shared variance analysis utilities.
- Added baseline-vs-economy comparison and economy calibration tooling.
- Improved vLLM compatibility for OpenAI-style chat completions and model visibility checks.
- Added recommended scale configs (Ollama and vLLM) and one-command vLLM research automation.

### P0 Safety / Validity Upgrades
- **Strict runtime preflight** (`src/runtime/preflight.py`): checks model backend readiness and aborts invalid runs.
- **Explicit unsafe override** (`--allow-stub`) added to demos for development-only fallback runs.
- **Judge variance gate** in tournament demo (`--gate-judge-variance`) with configurable thresholds.
- Preflight now validates vLLM model exposure from `/v1/models` when available.

### P1 Experiment Infrastructure
- Added shared judge variance analyzer:
  - `src/analysis/judge_variance.py`
- Upgraded stress test script:
  - `tests/stress_judge_variance.py` (configurable model/runs/thresholds + JSON report)
- Added paired condition runner:
  - `tests/reproduce_baseline_vs_economy.py`
- Added economy derivation utility:
  - `src/economy/calibration.py`
  - `tests/derive_economy_params.py`

### vLLM Integration Improvements
- `src/models/vllm_backend.py`:
  - Added `VLLM_BASE_URL` and optional `VLLM_API_KEY` support.
  - Switched primary path to `/v1/chat/completions` with JSON response format support.
  - Added compatibility fallback to `/v1/completions`.
  - Added model listing helper for preflight validation.
- `src/models/judge.py`:
  - Added vLLM handling in `generate_judgment()` for consensus/instructor path.
  - Fixed unload cleanup for vLLM handle.
- `demo_tournament.py`:
  - Properly honors `judge_type` (`single`, `ensemble`, `consensus`) instead of always single judge.

### Runtime and Config Fixes
- `demo_dynamic.py` and `demo_tournament.py` now preserve backend prefixes in model paths (no forced `ollama:` rewrite).
- `src/models/debater.py` now correctly initializes vLLM backend in `load_model()`.
- `src/arena/tournament.py` now uses configured `max_iterations` (removed hardcoded value).
- `src/config_loader.py` now reads YAML with `encoding='utf-8-sig'` for BOM-safe loading.

### Documentation Reconciliation
- Rewrote/updated:
  - `README.md`
  - `docs/PROCEDURES.md`
  - `docs/CONTRIBUTING.md`
  - `docs/architecture.md`
- Aligned docs to actual decisions (`RESPOND/PASS` + `use_search`), strict-mode behavior, and current run commands.

### New Recommended Artifacts
- Recommended Ollama tournament config (run-now path):
  - `configs/ollama_tournament_recommended.yaml`
- Recommended vLLM tournament config:
  - `configs/vllm_tournament_recommended.yaml`
- Added scripts:
  - `scripts/start_vllm_docker.ps1`
  - `scripts/run_research_tournament.ps1`
  - `scripts/run_vllm_research.ps1`

### One-Command vLLM Research Script
- `scripts/run_vllm_research.ps1` now:
  - Starts vLLM Docker container.
  - Waits for readiness.
  - Runs judge variance test.
  - Runs tournament with variance gate.
  - Archives timestamped artifacts.
  - Emits compact summary JSON:
    - `logs/vllm_research_summary_<timestamp>.json`

### Test and Verification Outcomes
- `python tests/test_suite.py`: **8 passed, 0 failed**.
- Strict mode validation works:
  - Blocks unavailable vLLM runs by default.
  - Allows explicit fallback only with `--allow-stub`.
- Judge variance stress script verified on stub and Ollama models.
- Tournament demos execute end-to-end in fallback mode when backend unavailable.
- Preflight passes against installed local Ollama models (`qwen2.5:7b` path validated).

### Decisions
- **DEC-027**: Experiment mode defaults to fail-fast on backend invalidity; fallback requires explicit opt-in.
- **DEC-028**: Judge variance is a gate for serious tournament runs, not just a diagnostic report.
- **DEC-029**: Separate "run-now" Ollama scale path from stricter vLLM scale path to maintain momentum without compromising data quality controls.

---

# Development Log: Token-Debate Experiment

*Chronological log of development progress*

---
## 2026-02-20 | Session 23: vLLM Migration & Truth-Based Tournament Setup

### What Happened
- Successfully migrated the inference backend from Ollama to **vLLM** to unlock high-performance parallel generation.
- Configured a **10-question truth-based tournament** to evaluate model grounding on AI ethics/alignment topics.

### Implementations
1. **vLLM Integration (`vllm_backend.py`)**
   - Implemented `VLLMBackend` using vLLM's OpenAI-compatible `/v1/completions` API.
   - Designed for significantly higher throughput via batching (vLLM's core strength).
2. **Unified Backend Architecture (`debater.py`, `judge.py`)**
   - Refactored `Debater` and `LLMJudge` to use a unified `_generate()` / `_generate_async()` helper system.
   - Removed duplicate logging/parsing logic across backends.
   - Added `vllm:` prefix routing in `load_model()`.
3. **Truth Tournament Configuration**
   - Updated `tournament_config.yaml` with 10 challenging factual/ethical topics.
   - Shifted default models to vLLM-hosted Qwen2.5-1.5B-Instruct.

### Insights & Thoughts
- **Throughput as a Feature:** vLLM isn't just a speed fix; it's what makes 10-round tournaments with iterative betting viable. Ollama's sequential nature was a bottleneck for the "economy-at-scale" vision.
- **Architectural Cleanup:** The backend refactor fixed a creeping technical debt where `ollama` logic was bleeding into the `Debater` class. The new unified interface makes the models backend-agnostic.
- **Truth Grounding:** Moving from "opinion topics" (Session 22) to "truth topics" is the ultimate test of the economy. If agents can "bet on truth," the economy becomes a verification layer.

### Key Decisions
- **DEC-042**: **OpenAI-Compatibility over Custom API** — Opted for the OpenAI REST standard for vLLM to ensure future-proofing against other provider APIs (Anthropic, DeepSeek).
- **DEC-043**: **Consolidated Generation** — Decided to enforce a single `_generate` entry point in models to ensure thinking extraction and cost tracking are applied consistently regardless of the backend.

---

### What Happened
- Successfully designed and implemented **DEC-038: The Wallet Phase** to fix the "Blind Betting" and "Argument Amnesia" architectural flaws that prevented economy grounding.
- Transitioned the debater from a completely blind bettor to an agent that explicitly models a `max_budget` for each turn, threading that awareness into the generation phase.

### Implementations
1. **Budget Authorization in Deliberation**
   - Modified `BetDecision` and `DeliberationResponse` to include `max_budget`.
   - Updated the `decide_bet` prompt to explicitly ask the model: "How many tokens can you afford to spend? Is it worth the cost?"
   - The model now outputs its budget request alongside the bet amount in its JSON decision.
2. **Threading the Strategy and Budget**
   - In `dynamic_round.py`, `_process_bet` now converts `max_budget` into an LLM context token limit (applying the `token_cost_ratio`).
   - The `<thinking>` from deliberation is captured as `strategy_context` and passed into generation.
3. **Constrained Generation Limits**
   - Updated `generate_argument()` and `generate_research()` in `debater.py` to enforce `max_tokens = max_budget_tokens`.
   - The model's `<thinking>` is injected into the generation prompt, ensuring it remembers its strategic plan.

### Insights & Observations from 1.5b Verification Run
- **Mathematical Enforcement works:** Responses *are* getting physically cut off. The Ollama backend enforced the `max_tokens` limits. For example, Debater Beta authorized a budget, rambled too long, and its generation abruptly ended midsentence: "protecting individual privacy becomes paramount (Brown & Green, 2026). Governments should". This proves that if they want to finish their thoughts, they *must* learn to be concise or authorize higher budgets.
- **Mutual Pass on Low Balances:** The match naturally terminated via mutual pass on Iteration 5. Debater Alpha had 4 tokens, Debater Beta had 1 token. Because they had no funds left to wage effective arguments, the logic gracefully concluded the debate, proving the economy genuinely drives the termination state when generation costs drain the banks.
- **Emergence of Economic Thinking:** In the baseline test (Session 20), models mentioned economy words in `<thinking>` only 1 time. After implementing the Wallet Phase, the 1.5b models outputted **8 mentions** (4 per debater) of the economy. They are actively reading their balances.

### Key Decisions
- **DEC-041**: **Hard limit over organic length** — Decided to strictly enforce `max_tokens` rather than relying on the model to "naturally" stop generating. Autoregressive models lack the internal capacity to count words mid-generation; they must set a limit upfront.
## 2026-02-20 | Session 21: Pre-Tournament Safeguards & Structural Testing

### What Happened
- Shifted focus to **validation infrastructure** before running more large-scale tournaments.
- Recognized the need for rapid feedback loops that don't rely on full 15-minute tournament runs.
- Addressed the "chicken-and-egg" problem: needing tournament data to validate the system, but needing a valid system to trust tournament data.

### Implementations
1. **Stress Tests (The Validation Suite)**
   - Created `tests/stress_judge_symmetry.py`: Verifies judge isn't biased by argument position by feeding identical arguments.
   - Created `tests/stress_judge_discrimination.py`: Verifies judge heavily penalizes clear gibberish vs a strong argument.
   - Created `tests/stress_economy_bankruptcy.py`: Verifies the ledger strictly enforces the `max_debt` ceiling when punitive flat fees are applied.
2. **Health Check Observer (`HealthCheckObserver`)**
   - Added passive tracking for pathological behaviors mid-tournament (`ALL_PASS`, `HIGH_VALIDATION_FAILURE`, `ZERO_BETS`).
   - Enabled by default in `demo_dynamic.py`.
3. **Round Checkpoints**
   - Modified `Tournament` execution loop to print human-readable narrative snapshots from observers between rounds.

### Key Decisions
- **DEC-039**: **Metrics decoupled from core loop** — Health checks and analytical narratives exist entirely in the Observer layer (`observers.py`), ensuring the core `DynamicDebateRound` remains clean and free of side-effects.
- **DEC-040**: **Strategic Deferrals** — The "AI-run Bank" (credit/debt manager) and "vLLM migration" (for speed) are officially deferred. Reason: The AI Bank adds complexity before base economic grounding is solved, and vLLM threatens the current rapid-iteration prompt engineering occurring on Ollama.

---

## 2026-02-20 | Session 20: Economy Grounding & Wallet Phase Architecture

### What Happened
- Deep analysis revealed debaters (especially 7B and below) have **zero economic meta-awareness** and continuously burn tokens into bankruptcy without adjusting strategy.
- Identified the **Grounding Problem**: Providing abstract token balances isn't enough to induce scarcity behavior.
- Implemented **Feedback Injection**: `decide_bet` prompt now explicitly states token drops ("LAST TURN: You spent/lost X tokens").
- Added **Structured Metrics**: `MetricsObserver` now automatically tracks `economy_mentions` in the model's `<thinking>` tags to measure the effectiveness of grounding experiments.

### Key Architectural Discoveries (The Flaws)
1. **Blind Betting**: Debaters place a bet *before* generating an argument, meaning they bet without knowing their generation costs or argument quality.
2. **Argument Amnesia**: The `decide_bet` thinking phase is completely forgotten when `generate_argument` starts.

### Future Priority Plans
- **DEC-038**: **The Wallet Phase** — Replace the current dual-action deliberation prompt with a pure economic authorization phase ("You have X tokens. Authorize Y spend?"). The authorized budget (`max_budget_tokens`) must then be passed directly into the generation phase as a hard limit.

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
Active vs Passive:   65% vs 35% â† Active wins
Engaged vs Accurate: 61% vs 39% â† Engagement beats static accuracy
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



