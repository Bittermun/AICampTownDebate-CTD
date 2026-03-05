import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.benchmark import load_benchmark_policy, run_phase1
from src.benchmark.runner import _derive_claim_posture


def test_claim_posture_insufficient_seed_blocks_l2() -> None:
    claim_level, ready, blockers = _derive_claim_posture(
        final_pass=True,
        allow_stub=False,
        strict_runtime=True,
        dry_run=False,
        source_mode="default",
        degraded_mode=False,
        settlement_reconciled=True,
        score_provenance={
            "counterfactual": {
                "uplift_model_minus_fixture": {"positive_ci95": True}
            }
        },
        seed_count=1,
    )
    assert claim_level == "L1"
    assert ready is False
    assert any("insufficient_seeds" in b for b in blockers)


def test_run_phase1_dry_run_exposes_claim_fields() -> None:
    policy = load_benchmark_policy("configs/benchmark_phase1.yaml")
    result = run_phase1(
        policy=policy,
        tournament_config_path="configs/ollama_tournament_recommended.yaml",
        model_name="stub",
        judge_model_override="stub",
        seeds=[101],
        fixtures_dir="benchmarks/fixtures",
        allow_stub=True,
        dry_run=True,
    )
    payload = result.to_dict()
    assert payload["claim_level"] == "L0"
    assert payload["quality_claim_ready"] is False
    assert isinstance(payload["quality_claim_blockers"], list)
