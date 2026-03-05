# vLLM Transition Verification Plan

## Goal

Quantify the effect of moving benchmark/tournament execution from Ollama or generic OpenAI-compatible routes to `vllm:*` backends while preserving benchmark validity and settlement correctness.

## Success Criteria

- Runtime readiness: strict preflight passes for all configured debaters/judges.
- Quality validity: benchmark run reaches `L1` or better with no settlement mismatch.
- Performance gain: median wall-clock improvement and/or throughput increase vs baseline.
- Reproducibility: fixed seeds produce stable pass/fail and similar score distributions.

## A/B Matrix

Run the same seeds/topic sets under both conditions:

1. Baseline: current stable backend (`ollama:*` or existing `openai:*` route).
2. Candidate: `vllm:*` model/judge routed through endpoint roster.

Keep constant across A/B:

- `configs/benchmark_phase1.yaml`
- topic fixtures and source mode
- seeds, matrix labels, gate settings
- replacement policy and retries

## Execution Steps

1. Runtime probe and backend coverage snapshot.
2. Batch benchmark (baseline) with manifest + aggregate report.
3. Batch benchmark (vLLM candidate) with same configuration controls.
4. Governance checks on candidate artifacts:
   - score ceiling audit
   - settlement reconciliation
   - claim readiness decision
5. Compare A/B:
   - final pass rate
   - benchmark score
   - gate pass rates
   - runtime per run
   - bankruptcy/replacement incidence

## Commands (Template)

```bash
python tests/test_phase1_batch_endpoint_assignment.py
python tests/test_openai_compat_backend.py

python scripts/run_phase1_batch.py \
  --model-id "vllm:<MODEL>" \
  --judge-model "vllm:<MODEL>" \
  --seeds "101,202,303" \
  --matrix-labels "set01,set02" \
  --openai-base-urls "http://host1:8000,http://host2:8000"

python scripts/audit_score_ceiling.py \
  --config configs/benchmark_phase1.yaml \
  --fixtures-dir benchmarks/fixtures \
  --output logs/score_ceiling_audit.json

python scripts/reconcile_settlement.py \
  --transcript <transcript.json> \
  --ledger <ledger.json> \
  --output logs/reconcile_settlement_vllm.json
```

## Blindspots To Check

- Endpoint miswiring: `OPENAI_COMPAT_BASE_URL` set but `VLLM_BASE_URL` missing.
- False gains: shorter runs from early failures or degraded mode.
- Artifact staleness: reconciliation run against old transcript/ledger pair.
- Judge drift: calibration/variance gates changed by backend swap.
- Dataset leakage: fixture/source mode differences between A/B runs.

## Reporting Contract

Report at claim level:

- `L0`: mechanics broken.
- `L1`: valid run, no quality claim.
- `L2`: quality claim allowed by policy and evidence.

Do not report a quality improvement unless `L2` is achieved on strict, non-stub artifacts.
