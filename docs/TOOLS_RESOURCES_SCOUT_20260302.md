# Tools and Resource Scout (2026-03-02)

This list expands beyond packages: skills, external tools, datasets/benchmarks, and operational resources.
Priorities are aligned to `docs/STRATEGY_TOOL_SKILL_PRIORITIES_20260302.md` (measurement truth, ranking validity, scaling, hardening).

## Installed Skills (Now Available After Restart)

- `openai-docs` (official API/reference checks)
- `jupyter-notebook` (artifact analysis workflows)
- `spreadsheet` (tabular leaderboard and regression slicing)
- `pdf` (ingest papers/protocols)
- `doc` (repeatable docs/spec workflows)
- `security-threat-model` (hardening/adversarial planning)
- `lm-evaluation-harness` (benchmark integration workflow)
- `vllm` (serving + runtime tuning workflow)
- `mlflow` (experiment tracking workflow)
- `phoenix` (LLM observability workflow)
- `weights-and-biases` (tracking and dashboard workflow)
- `read-github` (GitHub docs/code MCP workflow; Windows compatibility patched)
- `context7` (up-to-date docs fetch; requires API key setup)

## High-Impact Tools To Try Soon (Top 10)

1. Inspect AI + inspect_evals
   - Type: Evaluation framework + task sets
   - Why: Strong fit for objective/agent-style evals and reproducible test plans.
   - Link: https://github.com/UKGovernmentBEIS/inspect_ai
2. lm-evaluation-harness
   - Type: Standard benchmark runner
   - Why: Direct path for replacing fixture-ceiling dependence with model-derived scoring.
   - Link: https://github.com/EleutherAI/lm-evaluation-harness
3. OpenAI Evals
   - Type: Eval framework/templates
   - Why: Useful baseline for structured eval contracts and regression gates.
   - Link: https://github.com/openai/evals
4. promptfoo
   - Type: Prompt/application regression + red-team testing
   - Why: Fast CI-friendly adversarial and policy checks before champion promotion.
   - Link: https://www.promptfoo.dev/
5. garak
   - Type: LLM vulnerability scanner
   - Why: Adds adversarial hard gates for jailbreaks/leakage and model safety regressions.
   - Link: https://github.com/NVIDIA/garak
6. MLflow
   - Type: Experiment tracking/model registry
   - Why: Strong artifact lineage for benchmark runs and promotion decisions.
   - Link: https://mlflow.org/
7. Arize Phoenix
   - Type: LLM traces/evaluation observability
   - Why: Good for judge drift, per-step trace debugging, and failure triage.
   - Link: https://phoenix.arize.com/
8. Weights & Biases
   - Type: Experiment dashboards and sweeps
   - Why: Good for fast comparison across seeds/config variants.
   - Link: https://wandb.ai/site
9. DVC
   - Type: Data/artifact versioning
   - Why: Reproducible dataset and benchmark artifact governance.
   - Link: https://dvc.org/
10. Bradley-Terry / skill rating utilities (`choix`, `openskill`, `trueskill`)
   - Type: Ranking/statistics building blocks
   - Why: Matches roadmap need for uncertainty-aware ranking and confidence-aware promotion.
   - Links:
     - https://github.com/lucasmaystre/choix
     - https://github.com/vivekjoshy/openskill.py
     - https://trueskill.org/

## Benchmark and Dataset Resources (High Value)

- LiveBench (freshness-oriented leaderboard/eval framing): https://livebench.ai/
- SWE-bench (software task benchmark): https://www.swebench.com/
- GAIA benchmark (agentic/tool-use difficulty): https://huggingface.co/gaia-benchmark
- MMLU-Pro (already in fixtures; keep alignment with upstream spec): https://github.com/TIGER-AI-Lab/MMLU-Pro
- TruthfulQA (already in fixtures; keep metric contract aligned): https://github.com/sylinrl/TruthfulQA

## Infrastructure/Orchestration Resources (Selective)

- SkyPilot (portable cloud/GPU orchestration): https://github.com/skypilot-org/skypilot
- Modal (quick hosted workloads for eval jobs): https://modal.com/
- OpenTelemetry (trace standards for multi-tool observability): https://opentelemetry.io/

## Large Backlog (Parked For Later)

- HELM: https://crfm.stanford.edu/helm/
- OpenCompass: https://github.com/open-compass/opencompass
- Hugging Face lighteval: https://github.com/huggingface/lighteval
- LangSmith: https://www.langchain.com/langsmith
- Prompt injection references (OWASP LLM Top 10): https://owasp.org/www-project-top-10-for-large-language-model-applications/
- Data lake versioning option (lakeFS): https://lakefs.io/
- Pipeline orchestration alternatives (Prefect, Dagster)

## Notes and Caveats

- `context7` is installed but not ready until `CONTEXT7_API_KEY` is set.
- `read-github` was patched locally for Windows (`npx.cmd` resolution).
- External skill catalogs vary in quality; prefer official docs or mature repos for production decisions.

## Reproducibility

- Bootstrap script: `scripts/bootstrap_agent_stack.ps1`
- Source lock: `docs/AGENT_STACK_LOCK_20260302.md`

## Suggested Adoption Sequence

1. Measurement truth: wire `lm-evaluation-harness`/Inspect for one model-derived metric end-to-end.
2. Ranking validity: introduce Bradley-Terry/uncertainty estimates with CI thresholds.
3. Hardening gate: add promptfoo + garak checks to promotion path.
4. Traceability: route runs to MLflow or Phoenix and keep artifact provenance strict.
