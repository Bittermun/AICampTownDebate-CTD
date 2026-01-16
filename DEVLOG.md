# Development Log

Append-only journal. Each session adds entries at the top.

---

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
