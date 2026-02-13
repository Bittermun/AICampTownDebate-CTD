# Project Handoff: AI Debate Experiment

## Status: Core Loop Stable (Phase: Core Complete)
The project has a stable core loop for dynamic debates, a functional token economy, and a multi-dimensional judge system.

## Key Breakthroughs
- **Dynamic Debate Duration**: Rounds end organically via LLM-driven "PASS" decisions rather than fixed turn counts.
- **Token Economy**: Debaters pay for research and refutation; they earn tokens through pot splits and winning bets.
- **ITMC (Inference-Time Mesa-Cognition)**: Debaters use `<thinking>` tags for private deliberation before making public statements or decisions.
- **Multi-Dimensional Judging**: Claims are scored on Accuracy, Responsiveness, and Argument Development.

## Recent Architectural Changes
- **EconomyParams**: Arena-specific economic settings have been moved to `EconomyParams` to avoid confusion with global `TournamentConfig`.
- **Roleless Prompts**: All debater prompts now use neutral framing to reduce performance volatility from role-playing.
- **Config Wiring**: `demo_dynamic.py` and `Tournament` now correctly respect YAML configuration for all economic and iteration parameters.

## Directory Structure (Refined)
- `src/arena/`: Core round and tournament orchestration.
- `src/models/`: LLM wrappers for debaters and judges.
- `src/economy/`: Token ledger, betting, and distribution logic.
- `src/logs/`: Transcript formatting and persistence.
- `tests/`: Consolidated verification and experimental scripts.

## Known Issues / Technical Debt
- **Ollama Context Management**: Long debates can hit context limits; current mitigation is basic self-summarization.
- **Positional Bias**: Judges can still show positional bias; `JudgeConfig.randomize_argument_order` helps but isn't a total cure.

## Next Priorities
1. **Parallel Tournaments**: Scaling system to run independent debates simultaneously.
2. **Web Search Tool**: Enhancing the `RESEARCH` action with actual real-time information retrieval.
3. **Advanced ITMC Analysis**: Aggregating thinking logs to measure debater "honesty" vs "strategic manipulation".
