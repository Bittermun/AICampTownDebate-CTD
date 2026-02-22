---
description: How to resume autonomous work on the Token-Debate Experiment project
---

# Resume Workflow

## 1. Orientation (30 seconds)
// turbo
Read the handoff document for current state:
```
cat C:\Users\msunw\.gemini\antigravity\brain\c700a180-0b1a-407f-a829-127ac9dd575c\handoff.md
```

## 2. Check What's Running
// turbo
```powershell
Get-Process python -ErrorAction SilentlyContinue | Select-Object Id,StartTime,CommandLine
```

## 3. Run the Regression Suite
// turbo
```powershell
python tests/test_suite.py
```
Must be 8/8 green before any changes.

## 4. Check Recent Logs
// turbo
```powershell
Get-ChildItem logs/*.json | Sort-Object LastWriteTime -Descending | Select-Object -First 5 Name,LastWriteTime
```

## 5. The Autonomous Loop
When working autonomously, follow this cycle:

```
┌─→ OBSERVE: Run tournament / analyze existing logs
│     python demo_tournament.py --config configs/vllm_tournament_recommended.yaml
│     python tests/distill_insights.py
│
├─→ HYPOTHESIZE: What should change based on the data?
│     Log hypothesis in DEVLOG.md
│
├─→ IMPLEMENT: Make the change (one small thing at a time)
│
├─→ VERIFY: Run test_suite.py (8/8 green)
│
├─→ LOG: Update DEVLOG.md with results and git commit
│
└─→ REPEAT
```

## 6. Speed: Use vLLM over Ollama
vLLM is significantly faster for batch inference. Use this config:
```powershell
python demo_tournament.py --config configs/vllm_tournament_recommended.yaml
```
If vLLM is not running, check `logs/vllm_pull.log` for setup status.
Fallback to Ollama if vLLM is unavailable:
```powershell
python demo_tournament.py --config configs/ollama_tournament_recommended.yaml
```

## 7. Key Files Reference
| File | Purpose |
|---|---|
| `demo_tournament.py` | Run a full tournament |
| `tests/distill_insights.py` | Analyze tournament results for the 3 puzzle questions |
| `tests/probe_meta_awareness.py` | Single-round diagnostic probe |
| `tests/test_suite.py` | Regression suite (must pass 8/8) |
| `tests/test_convex_reward.py` | Convex reward curve unit tests |
| `src/models/response_models.py` | `weighted_confidence()` — margin scoring, spread_factor |
| `src/models/judge_prompts.py` | Judge system prompt + comparative memory block |
| `src/models/judge.py` | Judge evaluate() — system_prompt override, prior_judgment |
| `src/arena/dynamic_round.py` | Dynamic round loop, convex rewards, iteration logic |
| `DEVLOG.md` | Changelog — ALWAYS log changes here |
| `logs/tournament_results.json` | Latest tournament output |
| `logs/tournament_metrics.json` | Latest tournament metrics |
| `logs/meta_awareness.json` | Latest probe diagnostic |

## 8. DEVLOG Format
When logging changes, use this format in DEVLOG.md:
```markdown
## [DATE] — [TITLE]
**Hypothesis:** What you thought would happen
**Change:** What you changed (file, function, values)
**Result:** What actually happened (data)
**Next:** What to try next
```
