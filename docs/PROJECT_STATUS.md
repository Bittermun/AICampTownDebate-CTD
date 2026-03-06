# Project Status: Ground-Truth Assessment

Last updated: 2026-03-04

This document provides an honest assessment of project readiness across key dimensions. Scores are based on reading actual code, not documentation claims.

## Readiness Scores

| Dimension | Score | Summary |
|-----------|------:|---------|
| End-to-end tournament | 75/100 | Core loop works. Known winner-field bug (cosmetic). Dead code clutters picture. |
| GPU readiness (ollama/vllm) | 65/100 | Backends functional, configs exist, no large-scale validated run artifacts saved. |
| Intel NPU readiness | 10/100 | Zero NPU-specific code. `openai_compat` backend could theoretically serve an NPU model, but nothing is wired or tested. |
| Research-ready training data | 50/100 | SFT/preference data generation exists. QLoRA trainer scaffolded with SFT + DPO stages. Evaluation harness built. Not yet run end-to-end. |
| Code correctness confidence | 70/100 | 22/22 tests passing. Economy audit checks pass. Judge gates real. Winner-field bug fixed. Dead code removed. Missing: CI pipeline. |
| Feature/benchmark testing | 50/100 | Benchmark exists with claim levels. Evolution campaign runnable. Missing: regression suite, baseline results, CI pipeline. |
| Non-arbitrariness | 70/100 | Most mechanisms grounded in economics/evolution/info theory. Gaps: token_cost_ratio, confidence clamping, max_iterations, split_pot amount. |
| Documentation accuracy | 40/100 | Significant drift between docs and code prior to this cleanup. Multiple docs reference things that don't exist or have moved. |

**Overall project readiness: ~55/100**

The arena works as a research tool for observing debate behavior. The gap to "train a competitive model" is significant — the training loop and evaluation pipeline don't exist yet.

## What Works Today

These can be used right now for research:

- **Tournament execution** with real models (ollama qwen2.5:7b recommended)
- **Judge quality gates** (variance + calibration checks before tournaments)
- **Config-driven experiments** with strict/fallback mode separation
- **Evolutionary campaigns** (mutate strategy profiles, select winners across generations)
- **Economy accounting** with per-round audit checks
- **Transcript export** (JSON + Markdown) with full deliberation/judgment traces
- **Cross-round strategy memory** (debaters accumulate playbook over rounds)
- **Selection health dashboard** (pass rate, aggression, entropy, adaptation metrics)
- **Multi-agent injection** (experimental: critique/synthesize peer drafts)

## What's Partially Built

These exist but have significant gaps:

| Component | What exists | What's missing |
|-----------|-------------|----------------|
| Training data pipeline | `src/training/contracts.py` builds SFT/preference pairs from traces | No training loop, no evaluation, `TrainerInterface` is an empty protocol |
| Trace analysis | `trace_contract.py` normalizes transcripts, `trajectory_parser.py` extracts per-debater data | Trajectory parser uses fragile emoji-based splitting, no longitudinal validation |
| Comparative lanes | 3 configs exist (full/emergent/baseline), orchestration script written | Configs untracked, script not integrated into benchmark runner |
| Bank agent | `src/economy/bank.py` has class structure | Imports missing module (`base_model`), will crash. Both core methods return stubs. Not wired into any code path. |

## Dead Code

These files exist but are not used by any active execution path:

| File | Status |
|------|--------|
| `src/arena/round.py` | Superseded by `DynamicDebateRound`. Not imported anywhere. |
| `src/models/judge_factory.py` | Never imported by any demo or runner. |
| `src/models/protocols.py` | Protocol definitions, never used at runtime. |
| `Debater.generate_research()` | Method exists but unreachable — research path goes through `generate_argument()`. |

## Known Bugs

| Bug | Impact | Location |
|-----|--------|----------|
| Winner field logic | `self._eliminated is False` is never true (it's `None` or string). Falls through to balance comparison which happens to be correct. Cosmetic but misleading. | `src/arena/tournament.py:save_results()` |
| `bank.py` import crash | `from ..models.base_model import BaseBackend` — `base_model.py` does not exist | `src/economy/bank.py` |
| DEVLOG session ordering | Session 25 appended at bottom instead of top (newest-first convention) | `DEVLOG.md` |
| Duplicate AGENT_FORUM entries | Campaign analysis from Antigravity appears twice with slightly different formatting | `AGENT_FORUM.md` |

## Untracked Files That Should Be Committed

| File | Why |
|------|-----|
| `configs/baseline_no_econ_config.yaml` | Ablation config for "no economy" condition |
| `configs/emergent_base_config.yaml` | Ablation config for "emergent, no rails" condition |
| `configs/multi_agent_experimental.yaml` | Referenced in README run commands |
| `docs/MULTI_AGENT_EXECUTION_PROTOCOL_20260305.md` | Referenced in HANDOFF as required reading |
| `scripts/check_agent_ownership.py` | Multi-agent workflow governance |
| `scripts/run_comparative_lanes.py` | 3-lane comparative experiment orchestration |
| `tests/test_benchmark_claim_governance.py` | Tests claim posture logic |
| `tests/test_debater_multi_agent.py` | Tests multi-agent injection |
| `tests/test_reconcile_settlement.py` | Tests settlement reconciliation |
| `tests/test_run_tournament_batch_resume.py` | Tests batch checkpoint/resume |

Files to skip: `tmp_recon/` (scratch data), `src/economy/bank.py` (broken, would confuse).

## Non-Arbitrariness Audit

**Score: 70/100** — Most mechanisms have principled grounding, but several parameters lack derivation.

### Well-Grounded Mechanisms

- **Betting fees** — transaction cost analogy from market microstructure
- **Kelly criterion sizing** — information-theoretically optimal growth rate
- **Multi-dimension judging** — accuracy/responsiveness/development measure distinct constructs
- **Scaling fees** — mechanism design for convergence incentives
- **Bankruptcy** — evolutionary selection, not penalty
- **Confidence-proportional payout** — pari-mutuel market structure
- **Wallet Phase** — forces explicit budget authorization, grounded in resource allocation theory
- **Sqrt convex reward curve** for bet resolution — rewards improvement with diminishing returns

### Arbitrary or Weakly-Grounded Parameters

| Parameter | Current value | Issue |
|-----------|---------------|-------|
| `token_cost_ratio` | 20:1 | Tuning parameter, not derived from cost curves |
| Confidence clamp | 5-95% | Practical guard, range not derived from judge noise measurement |
| `max_iterations` | Config-set | Safety cap, doesn't emerge from economics (fees should handle this) |
| `split_pot` initial bounty | Config-set amount | Prevents zero-payout, but amount is arbitrary |
| Fee cap | 50% | Prevents lockout, but the specific value is a design choice |
| `token_cost_ratio` portability | Assumed constant | Same ratio used across backends/models with different token efficiencies |

### How to Improve

1. Derive `token_cost_ratio` from empirical generation cost curves per model
2. Set confidence clamp bounds from observed judge noise distribution
3. Test whether `max_iterations` can be removed entirely (rely on fee pressure + bankruptcy)
4. Derive initial bounty amount from survival runway targets
5. Calibrate fee cap from observed convergence behavior

## Gap Analysis: Path to Goals

### Goal 1: Train a Competitive Model

| Step | Status | Next action |
|------|--------|-------------|
| Generate debate traces | Working | Run 50+ rounds with 7b judge for research-grade data |
| Export training data | Working | `src/training/contracts.py` produces SFT + preference pairs |
| Validate trace quality | Not started | Need metrics for whether traces are better than unconstrained generation |
| Training loop | Not started | Need to choose framework (QLoRA on 1.5b fits RTX 4070 8GB) |
| Evaluation pipeline | Not started | Need held-out task set to measure if trained model improves |
| Compare to baseline | Not started | Need unconstrained-debate training data as control condition |

### Goal 2: Observe Emergent Behavior

| Signal | Status | Evidence |
|--------|--------|----------|
| Economy awareness | Confirmed | 8x increase in economy mentions after Wallet Phase |
| Adaptation after loss | Weak positive | +0.020 adaptation gain with ADAPT_ON_LOSS directive |
| Budget optimization | Partial | Models authorize budgets but pass rate too high (0.83 vs ~0.35 target) |
| Strategy differentiation | Not measured | No per-topic strategy analysis yet |
| Cross-round learning | Implemented | Strategy memory exists but not validated for behavioral impact |

## Hardware Context

- Development machine: RTX 4070 Laptop (8GB VRAM)
- QLoRA on 1.5b: comfortable fit
- QLoRA on 7b: tight but feasible
- Ollama qwen2.5:7b: runs locally for tournaments
- Intel NPU: available on machine but no software path exists
