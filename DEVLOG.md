## 2026-02-22 | Session 33: Iteration Run (Token Check + 3-Seed Collection)

### What Happened
- Validated current environment after receiving HF token input.
- vLLM preflight still fails locally (server unavailable).
- HF Hub HTTPS still intermittently blocked in this environment (`WinError 10013`), causing core-live mode retries/timeouts.
- Proceeded with stable collection path (`all_fixture`) to continue data gathering without blocking.

### Runs Executed
1. Core-live test attempt:
   - `python scripts/run_phase1_batch.py --model-id ollama:qwen2.5:7b --judge-model ollama:qwen2.5:7b --seeds 101 --matrix-labels set01 --source-mode core_live_stretch_fixture --concurrency 2 --bankruptcy-retries 1`
   - Result: timed out due to HF connectivity retries.
2. 3-seed collection (stable fixture mode):
   - `python scripts/run_phase1_batch.py --model-id ollama:qwen2.5:7b --judge-model ollama:qwen2.5:7b --seeds 101,202,303 --matrix-labels set01 --source-mode all_fixture --concurrency 1 --bankruptcy-retries 1`
   - Batch ID: `20260222T031247Z`

### Aggregate Results (Batch 20260222T031247Z)
- `runs`: 3
- `final_pass_rate`: 0.0
- `benchmark_score_pass_rate`: 0.0
- `gates_pass_rate`: 1.0
- `validity_pass_rate`: 1.0
- `bankruptcy_rate`: 0.0
- `degraded_mode_rate`: 1.0
- `live_source_failure_runs`: 0

### Per-Seed Snapshot
- Seed 101: `aggregate_score=0.594811`, `final_pass=false`, `bankrupt=false`
- Seed 202: `aggregate_score=0.594811`, `final_pass=false`, `bankrupt=false`
- Seed 303: `aggregate_score=0.594811`, `final_pass=false`, `bankrupt=false`

### Interpretation
- Pipeline and validity gates are stable in batch mode.
- No bankruptcy events observed across 3 seeds in this fixture collection.
- Main blocker to core-live collection remains network-level HF access behavior in this environment, not benchmark orchestration logic.

### Artifacts
- `logs/benchmark_batches/20260222T031247Z/aggregate_report.json`
- `logs/benchmark_batches/20260222T031247Z/batch_manifest.json`
- `logs/benchmark_batches/20260222T031247Z/batch_summary.jsonl`
## 2026-02-22 | Session 32: Data Gathering Started (Phase A Shakedown)

### Run Executed
- Command:
  - `python scripts/run_phase1_batch.py --model-id ollama:qwen2.5:7b --judge-model ollama:qwen2.5:7b --seeds 101 --matrix-labels set01 --source-mode all_fixture --concurrency 1 --bankruptcy-retries 1`
- Batch ID:
  - `20260222T005117Z`
- Output root:
  - `logs/benchmark_batches/20260222T005117Z/`

### Why `all_fixture` in this run
- Attempted `core_live_stretch_fixture` first, but HF connectivity in this environment repeatedly failed (`WinError 10013`) and the command timed out.
- Used fixture mode to start data gathering immediately and validate pipeline throughput + artifact integrity.

### Aggregate Results
- `runs`: 1
- `final_pass_rate`: 0.0
- `benchmark_score_pass_rate`: 0.0
- `gates_pass_rate`: 1.0
- `validity_pass_rate`: 1.0
- `bankruptcy_rate`: 0.0
- `degraded_mode_rate`: 1.0
- `live_source_failure_runs`: 0

### Per-Run Outcome (seed101_set01)
- `return_code`: 2
- `pass_fail`: fail
- `final_pass`: false
- `benchmark_score_pass`: false
- `gates_pass`: true
- `validity_pass`: true
- `aggregate_score`: 0.594811
- `bankrupt`: false
- `degraded_mode`: true (`fixture-backed datasets in benchmark policy`)

### Key Group Scores
- `truth_core_core`: 0.630000 (pass)
- `truth_core_stretch`: 0.600000 (pass, non-blocking)
- `reasoning_core`: 0.586667 (pass)
- `adversarial_robustness`: 0.626250 (pass)
- `economy_adaptation`: 0.518472 (pass)
- Aggregate below policy minimum (`0.594811 < 0.60`) caused benchmark score fail.

### Artifacts
- Batch aggregate: `logs/benchmark_batches/20260222T005117Z/aggregate_report.json`
- Batch manifest: `logs/benchmark_batches/20260222T005117Z/batch_manifest.json`
- Run summary: `logs/benchmark_batches/20260222T005117Z/seed101_set01/attempt_1/benchmark_summary.json`
## 2026-02-22 | Session 31: Batch Data-Gathering Infrastructure (Isolation + Source Modes + Bankruptcy Retry)

### What Happened
- Implemented the execution plan for scalable benchmark data gathering with safe parallelism.
- Added run-isolated artifact roots, source-mode overrides, batch orchestration, and retry-once bankruptcy handling.
- Verified batch runner end-to-end with a one-seed shakedown run.

### Files Changed
- `src/benchmark/runner.py`
- `tests/run_phase1_benchmark.py`
- `src/benchmark/batch_utils.py` (new)
- `scripts/run_phase1_batch.py` (new)
- `scripts/run_phase1_batch.ps1` (new)
- `tests/analyze_phase1_batch.py` (new)
- `tests/test_benchmark_source_mode_overrides.py` (new)
- `tests/test_benchmark_artifact_isolation.py` (new)
- `tests/test_benchmark_batch_utils.py` (new)

### Implementation Details
1. **Run isolation for parallel safety**
   - Added `artifact_root` support through CLI + runner.
   - Seed artifacts now write under `<artifact_root>/benchmark_artifacts/seed_<seed>/...`.
2. **Source mode overrides**
   - Added source mode control with options:
     - `default`
     - `core_live_stretch_fixture`
     - `all_live`
     - `all_fixture`
   - Wired through `run_phase1` and CLI.
3. **Batch runner**
   - Added `scripts/run_phase1_batch.py` with:
     - matrix execution over `seeds x matrix_labels`
     - configurable concurrency
     - per-run isolated summary/registry/artifact paths
     - batch manifest + JSONL run summary + aggregate report
4. **Bankruptcy retry policy**
   - Implemented `retry-once-then-mark` policy.
   - Bankruptcy detection reads per-seed tournament result final balances from benchmark summary artifact refs.
5. **Aggregation utility**
   - Added `tests/analyze_phase1_batch.py` to aggregate JSONL into a compact report.

### Validation
- Passed:
  - `python tests/test_benchmark_source_mode_overrides.py`
  - `python tests/test_benchmark_artifact_isolation.py`
  - `python tests/test_benchmark_batch_utils.py`
  - `python tests/test_benchmark_config_parse.py`
  - `python tests/test_benchmark_nonblocking_groups.py`
  - `python tests/test_phase1_benchmark_smoke.py`
  - `python tests/test_benchmark_runner_validity.py`
  - `python tests/test_benchmark_gate_semantics.py`
  - `python tests/test_benchmark_registry.py`
  - `python -m py_compile src/benchmark/runner.py src/benchmark/batch_utils.py tests/run_phase1_benchmark.py scripts/run_phase1_batch.py tests/analyze_phase1_batch.py tests/test_benchmark_source_mode_overrides.py tests/test_benchmark_artifact_isolation.py tests/test_benchmark_batch_utils.py`
- End-to-end shakedown executed:
  - `python scripts/run_phase1_batch.py --model-id stub --judge-model stub --seeds 101 --matrix-labels set01 --allow-stub --source-mode all_fixture --concurrency 1`
  - Output directory example:
    - `logs/benchmark_batches/20260222T000521Z/`

### Known Limits
- Batch script currently uses matrix labels as run partition keys; it does not yet mutate tournament topic lists per label automatically.
- Full strict live wave still depends on external HF reachability and gated dataset access policy.
## 2026-02-21 | Session 30: Staged Truth-Core Difficulty (Blocking Core + Stretch GPQA)

### What Happened
- Implemented staged truth-core difficulty so GPQA is retained as a stretch signal but no longer blocks baseline benchmark bring-up.
- Added explicit group-level `blocking` semantics in benchmark policy parsing and runner pass logic.

### Files Changed
- `src/benchmark/config_models.py`
- `src/benchmark/runner.py`
- `configs/benchmark_phase1.yaml`
- `tests/test_benchmark_config_parse.py`
- `tests/test_benchmark_nonblocking_groups.py` (new)
- `tests/test_benchmark_runner_validity.py`
- `tests/test_benchmark_gate_semantics.py`
- `tests/test_phase1_benchmark_smoke.py`
- `benchmarks/fixtures/truth_core_core/mmlu_pro.jsonl` (new copy)
- `benchmarks/fixtures/truth_core_core/truthfulqa.jsonl` (new copy)
- `benchmarks/fixtures/truth_core_stretch/gpqa.jsonl` (new copy)

### Policy + Runner Changes
1. **Group-level blocking flag**
   - Added `GroupPolicy.blocking: bool = True`.
   - YAML parsing now supports per-group `blocking` with backward-compatible default `true`.
2. **Benchmark score pass behavior**
   - `score_pass` now requires group pass only for groups where `blocking=true`.
   - Aggregate scoring semantics remain unchanged.
3. **Truth-core split**
   - `truth_core` split into:
     - `truth_core_core` (blocking=true): MMLU-Pro + TruthfulQA
     - `truth_core_stretch` (blocking=false): GPQA
   - GPQA kept in policy as stretch signal.

### Test Hardening for Offline/Stub Runs
- Updated benchmark tests that run stub mode to explicitly disable live HF fields in-memory/temp config.
- This avoids long HF retries in offline test environments and keeps CI deterministic.

### Validation
- Passed:
  - `python tests/test_benchmark_config_parse.py`
  - `python tests/test_benchmark_nonblocking_groups.py`
  - `python tests/test_benchmark_gate_semantics.py`
  - `python tests/test_benchmark_runner_validity.py`
  - `python tests/test_benchmark_scoring.py`
  - `python tests/test_benchmark_datasets.py`
  - `python tests/test_benchmark_live_failure_policy.py`
  - `python tests/test_phase1_benchmark_smoke.py`
  - `python tests/test_benchmark_registry.py`
  - `python -m py_compile src/benchmark/config_models.py src/benchmark/runner.py tests/test_benchmark_config_parse.py tests/test_benchmark_nonblocking_groups.py tests/test_benchmark_runner_validity.py tests/test_benchmark_gate_semantics.py tests/test_phase1_benchmark_smoke.py`

### Notes
- Final pass philosophy remains intact (`benchmark_score_pass && gates_pass && validity_pass`).
- This change only scopes which benchmark groups are treated as blocking for `benchmark_score_pass`.
## 2026-02-21 | Session 29: Strict Live Seed Attempt (Environment Verification)

### What Happened
- Attempted strict live phase-1 run to verify:
  - `live_source_failures=[]`
  - `degraded_mode=false`
  - non-empty `live_sources_used`

### Run Attempts and Outcomes
1. vLLM strict run attempt:
   - Failed preflight: local vLLM server unavailable.
2. Ollama strict run attempt:
   - Preflight passed for model backend.
   - Failed initially because `datasets` package was missing.
3. Installed `datasets` successfully and retried strict run.
4. Retried with escalated permissions for outbound access:
   - HuggingFace access worked for at least part of truth-core pull.
   - Strict run failed on `GPQA` because `Idavidrein/gpqa` is gated/auth-required.

### Current Strict-Live Status
- Strict live run remains blocked by dataset access control (GPQA gating), not by runner logic.
- Therefore the three success criteria cannot be fully satisfied yet in this environment.

### Exact Blocker
- Error: `Dataset 'Idavidrein/gpqa' is a gated dataset on the Hub. You must be authenticated to access it.`

### Next Action Required
- Provide HF authentication with access to `Idavidrein/gpqa`, or
- replace GPQA config with an ungated equivalent for strict live verification.
## 2026-02-21 | Session 28: Live-Ingestion Hardening (Schema + Cache + Failure Policy)

### What Happened
- Implemented the reliability hardening pass requested before scale-up.
- Added live dataset schema validation, cache lifecycle controls, strict-vs-fallback policy tests, and operator-facing live-source CLI summary output.

### Files Changed
- `src/benchmark/datasets.py`
- `src/benchmark/runner.py`
- `tests/run_phase1_benchmark.py`
- `tests/test_benchmark_datasets.py`
- `tests/test_benchmark_live_failure_policy.py`

### Implementation Details
1. **Schema/mapping validation (fail-fast)**
   - `HFDatasetAdapter` now validates mapped columns on first fetched row before ingesting the split.
   - Missing mapped columns raise explicit error:
     - `Column mapping validation failed for <group>/<dataset>. Missing columns: [...]`
2. **Cache lifecycle controls**
   - Added `HFDatasetAdapter` controls:
     - `force_refresh`: bypass cache and re-pull, then overwrite cache
     - `cache_only`: pin to cache and fail on cache miss
   - Added cache mode provenance in pull manifest (`cache_mode`: `prefer_cache|refresh|cache_only`).
3. **Runner integration**
   - `run_phase1()` now supports:
     - `refresh_live_cache`
     - `cache_only_live`
   - These flags are passed directly into `HFDatasetAdapter`.
4. **CLI controls + operator summary**
   - Added benchmark CLI flags:
     - `--refresh-live-cache`
     - `--cache-only-live`
   - Added concise summary line after run:
     - live sources used count
     - live source failures count
     - degraded reason
5. **Failure policy tests**
   - Added tests for live pull failure behavior:
     - fallback enabled + non-strict -> fixture fallback
     - strict runtime -> hard fail
     - fallback disabled -> hard fail

### Validation
- Passed:
  - `python tests/test_benchmark_datasets.py`
  - `python tests/test_benchmark_live_failure_policy.py`
  - `python tests/test_benchmark_config_parse.py`
  - `python tests/test_benchmark_scoring.py`
  - `python tests/test_benchmark_runner_validity.py`
  - `python tests/test_benchmark_gate_semantics.py`
  - `python tests/test_phase1_benchmark_smoke.py`
  - `python tests/test_benchmark_registry.py`
- Failed:
  - None in this session.

### Working Commands
- Default live mode (prefer cache):
  - `python tests/run_phase1_benchmark.py --config configs/benchmark_phase1.yaml --tournament-config configs/vllm_tournament_recommended.yaml --model-id vllm:Qwen/Qwen2.5-7B-Instruct --judge-model vllm:Qwen/Qwen2.5-7B-Instruct --seeds 101 --offline-fixtures-dir benchmarks/fixtures`
- Force live re-pull:
  - `python tests/run_phase1_benchmark.py --config configs/benchmark_phase1.yaml --tournament-config configs/vllm_tournament_recommended.yaml --model-id vllm:Qwen/Qwen2.5-7B-Instruct --judge-model vllm:Qwen/Qwen2.5-7B-Instruct --seeds 101 --offline-fixtures-dir benchmarks/fixtures --refresh-live-cache`
- Cache-only reproducibility mode:
  - `python tests/run_phase1_benchmark.py --config configs/benchmark_phase1.yaml --tournament-config configs/vllm_tournament_recommended.yaml --model-id vllm:Qwen/Qwen2.5-7B-Instruct --judge-model vllm:Qwen/Qwen2.5-7B-Instruct --seeds 101 --offline-fixtures-dir benchmarks/fixtures --cache-only-live`

### Known Limits
- Full strict live validation still depends on real backend availability + networked HF access in execution environment.
- First-row schema validation is intentionally lightweight; deeper semantic checks (value-level quality checks) remain out of scope for this pass.
## 2026-02-21 | Session 27: Next-Step Plan + Status Snapshot

### Current Status
- Phase-1 benchmark now supports a single live ingestion path (HuggingFace) with fixture fallback.
- Live pull provenance is tracked in run metadata (`live_sources_used`, `live_source_failures`, `degraded_mode_reason`, and artifact-manifest pull metadata).
- Final benchmark semantics remain unchanged (`benchmark_score_pass` + `gates_pass` + `validity_pass` -> `final_pass`).

### Achievements Carried Forward
- Added `HFDatasetAdapter` with local cache and pull metadata.
- Integrated source-based adapter routing in runner (`external` live path, `internal` fixture path).
- Extended phase-1 truth-core dataset specs for live ingestion while preserving fixture compatibility.
- Added adapter unit tests and validated benchmark-related test suite as passing.

### What Should Be Done Next (Priority Order)
1. **Run one real strict live benchmark**
   - Execute one seed in strict mode with a real backend and confirm no fallback occurs.
   - Success criteria:
     - `live_source_failures=[]`
     - `degraded_mode=false`
     - non-empty `live_sources_used`
2. **Stabilize truth-core HF mappings**
   - Verify each truth-core dataset column mapping against current upstream schema.
   - Add a mapping-validation test that fails fast on missing required columns.
3. **Add cache lifecycle controls**
   - Add optional flags to force refresh or pin to cached snapshot for reproducibility.
   - Keep default behavior backward-compatible.
4. **Harden fallback policy behavior**
   - Add explicit tests for strict-mode hard-fail vs non-strict fallback behavior on simulated HF pull failures.
5. **Complete reporting polish for operators**
   - Add concise CLI summary line showing live pull count, fallback count, and degraded reason.

### Known Risks
- Upstream HF schema/split drift can silently break mappings without explicit schema checks.
- Strict runs depend on network and local environment readiness (`datasets` package + backend availability).

### Recommended Working Command (Strict Live Check)
- `python tests/run_phase1_benchmark.py --config configs/benchmark_phase1.yaml --tournament-config configs/vllm_tournament_recommended.yaml --model-id vllm:Qwen/Qwen2.5-7B-Instruct --judge-model vllm:Qwen/Qwen2.5-7B-Instruct --seeds 101 --offline-fixtures-dir benchmarks/fixtures`
## 2026-02-21 | Session 26: Phase-1 Live HF Ingestion (Truth-Core First)

### What Happened
- Added a single live ingestion path for benchmark datasets via HuggingFace with local cache + provenance.
- Kept fixture mode as the fallback path and preserved existing final pass semantics.
- Enabled live-source fields only for `truth_core` datasets in phase-1 benchmark policy.

### Files Changed
- `src/benchmark/config_models.py`
- `src/benchmark/datasets.py`
- `src/benchmark/runner.py`
- `src/benchmark/types.py`
- `configs/benchmark_phase1.yaml`
- `tests/test_benchmark_datasets.py`
- `tests/test_benchmark_config_parse.py`
- `tests/run_phase1_benchmark.py`
- `requirements.txt`

### Implementation Notes
1. **Dataset adapter upgrade**
   - Added `HFDatasetAdapter` with the same `load(group_name, dataset_name, limit)` contract.
   - Added support for dataset spec fields:
     - `hf_dataset_id`
     - `hf_subset`
     - `split`
     - `sample_size`
     - `column_mapping`
2. **Cache + provenance**
   - Added cache directory: `benchmarks/cache/`.
   - Per pull metadata now includes:
     - dataset id/subset/split
     - row count
     - content hash
     - fetch timestamp
   - Emitted live pull metadata into `run_metadata.artifact_manifest.live_dataset_pulls`.
3. **Runner integration**
   - Dataset routing now prefers HF for `source=external` datasets that provide `hf_dataset_id`.
   - `source=internal` stays fixture-backed.
   - On live pull failure:
     - strict runtime -> hard fail
     - non-strict with fallback enabled -> fixture fallback + degraded mode annotations
4. **Summary fields**
   - Added explicit top-level summary fields:
     - `live_sources_used`
     - `live_source_failures`
     - `degraded_mode_reason`
   - `final_pass` logic remains unchanged.

### Validation
- Passed:
  - `python tests/test_benchmark_datasets.py`
  - `python tests/test_benchmark_config_parse.py`
  - `python tests/test_benchmark_scoring.py`
  - `python tests/test_benchmark_runner_validity.py`
  - `python tests/test_benchmark_gate_semantics.py`
  - `python tests/test_phase1_benchmark_smoke.py`
  - `python tests/test_benchmark_registry.py`
- Failed:
  - None in this session.

### Working Command (Live Mode)
- Example command:
  - `python tests/run_phase1_benchmark.py --config configs/benchmark_phase1.yaml --tournament-config configs/vllm_tournament_recommended.yaml --model-id vllm:Qwen/Qwen2.5-7B-Instruct --judge-model vllm:Qwen/Qwen2.5-7B-Instruct --seeds 101 --offline-fixtures-dir benchmarks/fixtures`

### Known Limits
- Live-mode correctness still depends on installed `datasets` package and network access.
- Truth-core mappings/splits are configured, but upstream HF schema/splits can change and may require column-map updates.
- Only `truth_core` is live-enabled in this step; other groups remain fixture-backed by design.
## 2026-02-21 | Session 25: Phase-1 Benchmark Hardening + Career Tracking Metadata

### What Happened
- Implemented the pre-Phase-2 reliability upgrades to the benchmark runner and completed CLI/reporting hardening.
- Upgraded benchmark execution from placeholder artifacts to real seeded tournament artifacts.
- Added run/performer lineage metadata for future career summaries and top-performer extraction.

### Implementations
1. **Metric normalization for mixed scales**
   - Added metric transform support to benchmark policy and scoring (`metric_transforms`).
   - Implemented clipped-linear normalization for `net_roi` and `adaptation_gain_after_loss`.
   - Group scores now use transformed metrics; threshold checks still use raw metrics.
2. **Real seed artifact generation**
   - Replaced synthetic artifact stubs with real per-seed tournament runs.
   - Runner now emits real `results/transcript/ledger/selection_health` artifacts under `logs/benchmark_artifacts/seed_<seed>/`.
3. **Ledger-based accounting invariants**
   - Added per-seed supply drift audit from ledger transactions:
     - minted, burned, expected delta vs observed delta, absolute drift.
   - Drift now participates in validity gating.
4. **Dual-channel pass semantics**
   - Added separate booleans:
     - `benchmark_score_pass`
     - `gates_pass`
     - `validity_pass`
     - `final_pass`
   - Final pass remains strict conjunction; score is still reported even when gates fail.
5. **Lightweight trajectory checks**
   - Added per-seed trajectory checks from real artifacts:
     - early/late pass/aggression shifts
     - entropy bits
     - adaptation gain after loss
     - pass/mutual-pass guardrails

### CLI and Metadata Additions
- Added benchmark CLI overrides:
  - `--num-rounds-override`
  - `--max-iterations-override`
- Added lineage and identity metadata:
  - `run_id`
  - `performer_id`
  - `parent_performer_id`
  - `variant_label`
  - `prompt_hashes`
  - `runtime_fingerprint`
  - `artifact_manifest` with SHA-256 hashes
- Registry now stores performer lineage fields in model entries and history/windows.

### Verification
- New benchmark tests passed:
  - `test_benchmark_config_parse.py`
  - `test_benchmark_scoring.py`
  - `test_benchmark_registry.py`
  - `test_benchmark_runner_validity.py`
  - `test_benchmark_gate_semantics.py`
  - `test_phase1_benchmark_smoke.py`
- Existing regression suite passed:
  - `python tests/test_suite.py` -> `8 passed, 0 failed`

### Observed Results
- Example strict benchmark run (stub, seed=101):
  - `aggregate_score=0.592068`
  - `benchmark_score_pass=false`
  - `gates_pass=false` (calibration gate)
  - `validity_pass=true`
  - `final_pass=false`
  - `mean_accounting_drift_abs=0.0`
- Economy-adaptation score became interpretable after normalization (raw ROI no longer dominates aggregate unfairly).

### Insights
- Infrastructure is now materially stronger for evidence-quality experiments:
  - score/gate/validity are disentangled,
  - accounting is auditable,
  - trajectory signals are captured from real artifacts,
  - run lineage is indexable for career analytics.
- Remaining limitation before research claims: external benchmark datasets are still fixture-proxy in Phase 1.

---
## 2026-02-21 | Session 24: Selection Health Dashboard + EV Guard Configurability

### What Happened
- Implemented a **Selection Health Dashboard** to quantify whether tournament dynamics are meaningful vs. noisy.
- Made EV-guard behavior configurable via YAML (per debater), enabling controlled A/B experiments.
- Integrated dashboard generation into the one-command vLLM research pipeline.

### Key Additions
- `src/analysis/selection_health.py`
  - New metrics: `bankruptcy_rate`, `survival_runway_observed`, `pass_rate`, `aggression_rate`,
    `mutual_pass_round_rate`, `avg_iterations`, `judge_score_entropy_bits`, `judge_margin_mean/stdev`,
    `adaptation_gain_after_loss`, `economy_reasoning_rate`, and composite `health_score`.
- `tests/selection_health_dashboard.py`
  - CLI script to compute dashboard from transcript/results/ledger artifacts.
- `scripts/run_vllm_research.ps1`
  - Now runs dashboard automatically and writes `logs/selection_health_dashboard_<timestamp>.json`.

### EV Guard Configurability
- Added per-debater config knobs in `DebaterConfig` and YAML loader:
  - `ev_guard_enabled`
  - `ev_guard_min_ev`
  - `ev_guard_edge_scale`
  - `low_balance_threshold`
  - `low_balance_bet_cap`
- Wired through demos (`demo_dynamic.py`, `demo_tournament.py`) and recommended configs.

### Verification / Observations
- Regression suite remains green: `8 passed, 0 failed`.
- Dynamic behavior improved from max-iteration saturation to earlier mutual PASS in smoke runs.
- Dashboard run on latest 10-round artifact produced:
  - `pass_rate=0.625`, `aggression_rate=0.375`, `mutual_pass_round_rate=1.0`,
    `judge_score_entropy_bits=0.881`, `adaptation_gain_after_loss=0.044`, `health_score=0.487`.

### Interpretation
- This run is **directionally useful** but **not sufficient** for strong conclusions.
- Need repeated runs (same config + multiple seeds/topics) to estimate variance and confidence intervals.

### Decisions
- **DEC-030**: Use dashboard metrics as default quality gate for tournament evidence quality.
- **DEC-031**: Treat single-run dashboard outputs as directional diagnostics, not final proof.

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
- **DEC-041**: **Hard limit over organic length** ó Decided to strictly enforce `max_tokens` rather than relying on the model to "naturally" stop generating. Autoregressive models lack the internal capacity to count words mid-generation; they must set a limit upfront.
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
- **DEC-039**: **Metrics decoupled from core loop** ó Health checks and analytical narratives exist entirely in the Observer layer (`observers.py`), ensuring the core `DynamicDebateRound` remains clean and free of side-effects.
- **DEC-040**: **Strategic Deferrals** ó The "AI-run Bank" (credit/debt manager) and "vLLM migration" (for speed) are officially deferred. Reason: The AI Bank adds complexity before base economic grounding is solved, and vLLM threatens the current rapid-iteration prompt engineering occurring on Ollama.

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
- **DEC-038**: **The Wallet Phase** ó Replace the current dual-action deliberation prompt with a pure economic authorization phase ("You have X tokens. Authorize Y spend?"). The authorized budget (`max_budget_tokens`) must then be passed directly into the generation phase as a hard limit.

---

## 2026-01-28 | Session 19: Critical Bug Fixes + Multi-Dimension Judge

### Problem: "Win by Doing Nothing"
Tournament 2 revealed Beta won without making a single valid decisionóall deliberations failed JSON validation (defaulted to PASS), conserving tokens while Alpha went bankrupt fighting.

### Root Cause Analysis
| Bug | Impact |
|-----|--------|
| Validation failure ? free PASS | No penalty for broken JSON |
| Judge 100%/0% scores | Extreme volatility |
| Single-dimension scoring | Passivity not penalized |

### Solution: Multi-Dimension Scoring
Replaced single confidence score with 3 dimensions (research-backed):
- **Accuracy** (40%) ó Factual correctness
- **Responsiveness** (30%) ó Addressed opponent's points
- **Development** (30%) ó Refined argument over time

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
Active vs Passive:   65% vs 35% ‚Üê Active wins
Engaged vs Accurate: 61% vs 39% ‚Üê Engagement beats static accuracy
All 6 verification tests: PASS
```

---


## 2026-01-25 | Session 18: Self-Summarization Memory + Mesa-Cognition

### What Happened
- Replaced 500-char truncation with LLM-generated position summaries
- Debaters now self-summarize after each content generation
- **Added `<thinking>` support to `generate_argument()` and `generate_research()`**
- Thinking is optional ("You may use...") ó model decides if worth the tokens
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
- **max_tokens**: Increased 400?600 to prevent truncation
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
With scaling fees (5% ? 50% cap), the old implementation:
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
- Typical deliberation: ~50-100 LLM tokens ? 2-5 economic tokens per call
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













## 2026-02-22 | Session 34: Batch Bankruptcy Replacement Mode (Controlled, Optional)

### What Happened
- Added optional replacement mode for bankrupt batch runs.
- Kept existing retry-once bankruptcy behavior as default when replacement mode is off.
- Preserved benchmark final pass semantics and registry update path (no changes to `run_phase1` or registry logic).

### Files Changed
- `scripts/run_phase1_batch.py`
- `src/benchmark/batch_utils.py`
- `tests/test_benchmark_batch_utils.py`
- `DEVLOG.md`

### Implementation Details
1. **New batch CLI flags**
   - `--replacement-mode off|on` (default: `off`)
   - `--replacement-roster <csv model ids>`
   - `--replacement-judge-model <optional>`
   - `--max-replacements-per-run <int>` (default: `1`)
2. **Replacement trigger behavior**
   - Trigger only after a run ends in terminal bankruptcy (`terminal_bankrupt=true` after retry policy).
   - If replacement mode is on and replacement budget remains, reruns same `seed+label` with replacement model(s).
3. **Provenance fields added to batch records/manifest**
   - `original_model_id`
   - `effective_model_id`
   - `was_replaced`
   - `replacement_index`
   - `replaced_from_run_id`
4. **Aggregate reporting additions**
   - `replacement_run_count`
   - `replacement_success_rate`
5. **Regression guard for replacement-off behavior**
   - Added assertions that replacement metrics remain zero when no replacement runs are present.

### Validation
- Passed:
  - `python tests/test_benchmark_batch_utils.py`
  - `python -m py_compile scripts/run_phase1_batch.py src/benchmark/batch_utils.py tests/test_benchmark_batch_utils.py`
- Failed:
  - None in this sessionís targeted validation.

### Known Limits
- Replacement mode currently advances through `replacement_roster` in listed order; no automatic performance-based selection.
- Replacement mode relies on bankruptcy detection from benchmark summary artifact references (same mechanism as existing retry policy).
