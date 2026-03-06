"""Run QLoRA training on debate trace data.

Usage:
    # Train from a benchmark summary artifact:
    python scripts/run_training.py \
        --summary logs/benchmark_summary.json \
        --config configs/training_qlora.yaml \
        --output-dir logs/training_run_001

    # Train from pre-built JSONL datasets:
    python scripts/run_training.py \
        --sft-data logs/training_data/sft_examples.jsonl \
        --preference-data logs/training_data/preference_pairs.jsonl \
        --config configs/training_qlora.yaml \
        --output-dir logs/training_run_001

    # SFT only (skip DPO):
    python scripts/run_training.py \
        --sft-data logs/training_data/sft_examples.jsonl \
        --config configs/training_qlora.yaml \
        --output-dir logs/training_run_001

    # Dry run (uses NoOpTrainer to test pipeline wiring):
    python scripts/run_training.py \
        --summary logs/benchmark_summary.json \
        --dry-run \
        --output-dir logs/training_dry_run
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import yaml

from src.training.data_prep import build_training_data_from_summary
from src.training.trainer_interface import NoOpTrainer
from src.training.checkpoint_registry import register_checkpoint

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Run QLoRA training on debate traces")
    parser.add_argument("--summary", help="Benchmark summary JSON (will extract training data)")
    parser.add_argument("--sft-data", help="Pre-built SFT JSONL dataset")
    parser.add_argument("--preference-data", help="Pre-built preference pairs JSONL dataset")
    parser.add_argument("--config", default="configs/training_qlora.yaml", help="Training config YAML")
    parser.add_argument("--output-dir", required=True, help="Output directory for checkpoints")
    parser.add_argument("--base-checkpoint", help="Resume from existing checkpoint")
    parser.add_argument("--registry", default="logs/checkpoint_registry.json", help="Checkpoint registry path")
    parser.add_argument("--dry-run", action="store_true", help="Use NoOpTrainer (no GPU needed)")
    parser.add_argument("--min-tier", default="tier_b", help="Minimum judge reliability tier for data filtering")
    args = parser.parse_args()

    # Load config
    config_dict = {}
    config_path = Path(args.config)
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8-sig") as f:
            config_dict = yaml.safe_load(f) or {}
        logger.info("Loaded training config from %s", config_path)
    else:
        logger.warning("Config not found at %s, using defaults", config_path)

    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    sft_path = args.sft_data
    pref_path = args.preference_data

    # Step 1: Extract training data from benchmark summary if needed
    if args.summary and (not sft_path or not pref_path):
        logger.info("Building training data from summary: %s", args.summary)
        data_dir = str(out_dir / "training_data")
        build_result = build_training_data_from_summary(
            summary_path=args.summary,
            output_dir=data_dir,
            min_tier=args.min_tier,
        )
        logger.info(
            "Built %d SFT examples, %d preference pairs from %d/%d traces",
            build_result.sft_count,
            build_result.preference_count,
            build_result.traces_selected,
            build_result.traces_total,
        )
        if not sft_path and build_result.sft_path:
            sft_path = build_result.sft_path
        if not pref_path and build_result.preference_path:
            pref_path = build_result.preference_path

    if not sft_path and not pref_path:
        logger.error("No training data available. Provide --summary, --sft-data, or --preference-data.")
        sys.exit(1)

    # Step 2: Run training
    if args.dry_run:
        logger.info("Dry run mode - using NoOpTrainer")
        trainer = NoOpTrainer()
    else:
        try:
            from src.training.qlora_trainer import QLoRATrainer, QLoRAConfig
            qlora_config = QLoRAConfig.from_dict(config_dict)
            trainer = QLoRATrainer(config=qlora_config)
            logger.info("Using QLoRA trainer with model: %s", qlora_config.base_model)
        except ImportError as e:
            logger.error("Cannot import QLoRA trainer: %s", e)
            logger.error("Install training deps: pip install -r requirements-training.txt")
            sys.exit(1)

    result = trainer.run(
        sft_dataset_path=sft_path,
        preference_dataset_path=pref_path,
        base_checkpoint_path=args.base_checkpoint,
        output_dir=str(out_dir),
        config=config_dict,
    )

    # Step 3: Report results
    logger.info("Training run %s completed", result.run_id)
    for stage in result.stages:
        status = "PASS" if stage.success else "FAIL"
        logger.info(
            "  Stage %s: %s | checkpoint=%s | metrics=%s",
            stage.stage, status, stage.checkpoint_path, stage.metrics,
        )
        if stage.notes:
            for note in stage.notes:
                logger.info("    %s", note)

    # Step 4: Register checkpoints
    for stage in result.stages:
        if stage.success and stage.checkpoint_path:
            record = register_checkpoint(
                registry_path=args.registry,
                trainer_name=trainer.name,
                checkpoint_path=stage.checkpoint_path,
                run_id=result.run_id,
                parent_checkpoint_id=None,
                metrics=stage.metrics,
                tags=[stage.stage, "qlora" if not args.dry_run else "dry_run"],
            )
            logger.info("Registered checkpoint: %s -> %s", record.checkpoint_id, record.checkpoint_path)

    # Save run result
    result_path = out_dir / "training_result.json"
    with open(result_path, "w", encoding="utf-8") as f:
        json.dump(result.to_dict(), f, indent=2)
    logger.info("Run result saved to %s", result_path)

    # Exit with error code if any stage failed
    all_passed = all(s.success for s in result.stages)
    if not all_passed:
        logger.error("One or more training stages failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
