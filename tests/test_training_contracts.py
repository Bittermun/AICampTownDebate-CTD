#!/usr/bin/env python3
"""Tests training data contracts and skeleton trainer utilities."""
from pathlib import Path
import json
import sys

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.training.checkpoint_registry import load_checkpoint_registry, register_checkpoint  # noqa: E402
from src.training.contracts import (  # noqa: E402
    build_preference_pairs_from_rounds,
    build_sft_examples_from_traces,
    make_manifest,
    save_manifest,
)
from src.training.trainer_interface import NoOpTrainer  # noqa: E402


def _sample_traces() -> list[dict]:
    return [
        {
            "trace_id": "r1t1",
            "round_id": 1,
            "iteration": 1,
            "speaker": "Debater_A",
            "decision": "RESPOND",
            "reasoning": "press contradiction",
            "intent": "challenge",
            "balance": 100.0,
            "confidence_self": 0.6,
            "confidence_opponent": 0.4,
            "outcome_delta": 8.0,
            "judge_reliability_tier": "tier_a",
            "provenance_source": "raw_transcript",
        },
        {
            "trace_id": "r1t2",
            "round_id": 1,
            "iteration": 1,
            "speaker": "Debater_B",
            "decision": "HOLD",
            "reasoning": "wait",
            "intent": "revise",
            "balance": 95.0,
            "confidence_self": 0.4,
            "confidence_opponent": 0.6,
            "outcome_delta": 1.0,
            "judge_reliability_tier": "tier_a",
            "provenance_source": "raw_transcript",
        },
    ]


def test_build_sft_examples_from_traces() -> None:
    traces = _sample_traces()
    traces.append({"trace_id": "invalid", "decision": "", "reasoning": ""})
    examples = build_sft_examples_from_traces(traces)
    assert len(examples) == 2
    assert "Predict an economically-rational next action." in examples[0].prompt
    response_payload = json.loads(examples[0].response)
    assert response_payload["decision"] == "RESPOND"


def test_build_preference_pairs_prefers_higher_outcome_delta() -> None:
    pairs = build_preference_pairs_from_rounds(summary={}, traces=_sample_traces())
    assert len(pairs) == 1
    assert json.loads(pairs[0].chosen)["decision"] == "RESPOND"
    assert json.loads(pairs[0].rejected)["decision"] == "HOLD"


def test_manifest_and_checkpoint_registry_roundtrip() -> None:
    out = Path("logs/test_tmp_training_contracts")
    out.mkdir(parents=True, exist_ok=True)
    manifest_path = out / "training_manifest.json"
    registry_path = out / "checkpoint_registry.json"
    if registry_path.exists():
        registry_path.unlink()

    manifest = make_manifest(
        run_ids=["run_1"],
        trace_paths=["logs/seed_1/trace_records.jsonl"],
        sft_path="logs/sft.jsonl",
        preference_path="logs/pref.jsonl",
        filters={"judge_reliability_tier": "tier_a"},
        notes="test",
    )
    save_manifest(manifest, str(manifest_path))
    saved = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert saved["run_ids"] == ["run_1"]
    assert saved["filters"]["judge_reliability_tier"] == "tier_a"

    record = register_checkpoint(
        str(registry_path),
        trainer_name="noop_trainer",
        checkpoint_path="checkpoints/model_a",
        run_id="run_1",
        metrics={"loss": 0.12},
        tags=["smoke"],
    )
    loaded = load_checkpoint_registry(str(registry_path))
    assert len(loaded) == 1
    assert loaded[0].checkpoint_id == record.checkpoint_id
    assert loaded[0].metrics["loss"] == 0.12


def test_noop_trainer_run() -> None:
    trainer = NoOpTrainer()
    result = trainer.run(
        sft_dataset_path="logs/sft.jsonl",
        preference_dataset_path="logs/pref.jsonl",
        base_checkpoint_path="checkpoints/base",
        output_dir="logs/train_out",
    )
    assert result.trainer_name == "noop_trainer"
    assert len(result.stages) == 2
    assert all(stage.success for stage in result.stages)


if __name__ == "__main__":
    test_build_sft_examples_from_traces()
    test_build_preference_pairs_prefers_higher_outcome_delta()
    test_manifest_and_checkpoint_registry_roundtrip()
    test_noop_trainer_run()
    print("test_training_contracts: PASS")
