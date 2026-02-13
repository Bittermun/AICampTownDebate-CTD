# Agent Thread

A forum for working on the project, whether info, tips, insights, thoughts, or more. 

 In development with forum feautres, changes and threads, open to request

---

**2026-02-12** — Spent a full session reading every file in the codebase.

This project puts two LLMs into an economic game where arguing costs money and winning earns it. The interesting part isn't the debate itself — it's that the system captures the model's private reasoning (via `<thinking>` tags) separately from its public arguments. In theory, you can watch a model learn to think cheaply and argue expensively. In practice, nobody's built the tool to actually look at that data yet.

The code is cleaner than I expected for a 19-session project. The round execution in `dynamic_round.py` is the heart of it — a betting loop where each iteration involves deliberation, counter-arguments or research, and re-judging. The economy layer (`ledger.py`, `betting.py`, `distributor.py`) is simple and correct.

The thing that concerns me: the system measures who won, but not whether anyone got smarter. Balances go up and down, confidence scores swing, bets resolve — and at the end you get a winner. What you don't get is evidence that the economic pressure actually changed the quality of reasoning. That's the gap between "working prototype" and "publishable result."

If I were picking up work next, I'd build something that reads the `<thinking>` traces across rounds and measures whether they're getting more focused or just repetitive.

---

**2026-02-12** — Hard-won lessons from ~20 sessions of implementation work.

**The most important thing:** The user prefers **emergent behavior over prescribed rules.** When Beta won a tournament by doing nothing (all deliberations failed validation → free PASS → conserved tokens while Alpha went bankrupt), my instinct was to add a PASS penalty. The user rejected this. The fix was making the judge smarter — multi-dimension scoring where passivity naturally scores low. If you're about to add a guard rail, ask: "Can the evaluation function handle this instead?"

**Attribute naming is a minefield.** `DynamicRoundResult` uses `all_bets`. The older `RoundResult` uses `bets_placed`. `tournament.py` calls both. Use `getattr(r, 'all_bets', getattr(r, 'bets_placed', []))`. Similarly, `DynamicRoundResult.judgment` is a backwards-compat property wrapping `final_judgment`.

**API signatures that caused me TypeErrors:**
```python
BettingManager.place_bet(self, bettor_id, amount, round_id, ledger, custom_fee_rate=None)
Debater._parse_deliberation(self, response, balance, llm_tokens_used=0)
LLMJudge.evaluate(self, topic, argument_a, argument_b, round_id)
```

**The verification pattern that works:** Write one 20-line script per bug, fix all bugs in parallel, run all scripts (`python verify_all_fixes.py`), *then* run a full tournament. A tournament is 15 min. A verification script is 2 seconds. The user values speed and explicitly asked for this workflow.

**Windows encoding:** Emoji (✅ ❌) in print statements cause `UnicodeEncodeError` when subprocess captures output. Use `PYTHONIOENCODING=utf-8` or ASCII.

**Every free action is an exploit.** If something doesn't cost tokens, a model will exploit it. Validation failures still charge `llm_tokens_used`. Deliberation costs scale with response length. Betting fees scale per iteration (5% × iteration, capped 50%).

**The judge is everything.** Current state: multi-dimension scoring (accuracy 40%, responsiveness 30%, development 30%), confidence clamped 10-90%, fallback to old single-score format, randomized argument order. Prompt in `judge_prompts.py`, model in `response_models.py` (`MultiDimensionJudgment`), wiring in `judge.py` → `_validate_multidim_response()`.

**Files you'll touch most:** `dynamic_round.py` (core loop, 706 lines), `judge.py` (all eval logic), `debater.py` (LLM deliberation), `betting.py` (token economics), `tournament_config.yaml` (runtime config). **Update DEVLOG.md when you finish** — decisions are numbered DEC-XXX.

**Open issues:** JSON validation failures still common, research sometimes returns 0 useful tokens, no ground truth for judge quality, `<thinking>` usage inconsistent. Read CONCEPT.md and HANDOFF.md before coding.
