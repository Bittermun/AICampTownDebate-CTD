# Procedures

## Equipment & Software
- PC with 16GB+ RAM (Windows 11)
- Ollama (local LLM inference server)
- LLM models: Qwen 2.5 (1.5B parameters) for debaters and judge
- Python 3.11+ with dependencies: pydantic, pyyaml, ollama, duckduckgo-search
- Custom debate framework (AICampTownDebate)

## Experimental Setup
1. Install Ollama and pull the target model (`ollama pull qwen2.5:1.5b`).
2. Install Python dependencies (`pip install -r requirements.txt`).
3. Configure debate parameters in `configs/tournament_config.yaml`:
   - Two debater agents using the same base model
   - One judge agent (same or different model)
   - Initial token balance: 200 per debater
   - Maximum debt allowed: 50 tokens
   - Token pool per round: 100 tokens
   - Maximum betting iterations per round: 5

## Procedure
1. Select a debate topic (e.g., "Should AI development be regulated by governments?").
2. Launch a debate session via `python demo_dynamic.py --config configs/tournament_config.yaml`.
3. The system automatically executes the following cycle per round:
   a. Each debater generates an opening argument (costs tokens proportional to LLM output length).
   b. The judge scores both arguments on three dimensions: factual accuracy (40%), responsiveness to opponent (30%), and argument development (30%).
   c. Each debater privately deliberates using `<thinking>` tags (hidden from judge), then chooses to REFUTE, RESEARCH, or PASS.
   d. If betting, the debater wagers tokens. The system generates a counter-argument or conducts web research (via DuckDuckGo).
   e. The judge re-evaluates. Winning bets earn payout; losing bets forfeit stake plus a scaling fee (5% × iteration number, capped at 50%).
   f. Steps c–e repeat until both debaters PASS or the maximum iteration limit is reached.
4. After all rounds, the system records final token balances, distributes remaining pot tokens proportionally, and saves a full transcript (JSON and Markdown) with all arguments, deliberations, judge reasoning, and economic outcomes.
5. Repeat across multiple topics and configurations to collect data.

## Variables
- **Independent variable**: Presence of economic pressure (token costs for actions, betting stakes, scaling fees)
- **Dependent variables**: Argument quality (judge scores across dimensions), token efficiency (confidence gain per token spent), reasoning compression (length and focus of `<thinking>` traces over iterations)
- **Controlled variables**: Same base model for both debaters, same judge prompt, randomized argument presentation order to judge, identical initial token balance, same debate topics across trials

## Data Collection
- Transcripts saved automatically to `logs/` (JSON for programmatic analysis, Markdown for human review)
- Observer metrics captured per round: ROI, aggression rate, pass rate, momentum shifts, validation fallback counts, elapsed time
- Token ledger records every transaction with timestamps and reasons
