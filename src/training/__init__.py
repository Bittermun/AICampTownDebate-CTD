"""Training pipeline interfaces, contracts, and QLoRA trainer."""

from .checkpoint_registry import (
    CheckpointRecord,
    load_checkpoint_registry,
    register_checkpoint,
    save_checkpoint_registry,
)
from .contracts import (
    PreferencePair,
    SFTExample,
    TrainingDatasetManifest,
    build_preference_pairs_from_rounds,
    build_sft_examples_from_traces,
    make_manifest,
    save_manifest,
)
from .data_prep import TrainingDataBuildResult, build_training_data_from_summary
from .trainer_interface import NoOpTrainer, TrainingRunResult, TrainingStageResult, TrainerInterface

__all__ = [
    "CheckpointRecord",
    "NoOpTrainer",
    "PreferencePair",
    "SFTExample",
    "TrainingDataBuildResult",
    "TrainerInterface",
    "TrainingDatasetManifest",
    "TrainingRunResult",
    "TrainingStageResult",
    "build_preference_pairs_from_rounds",
    "build_training_data_from_summary",
    "build_sft_examples_from_traces",
    "load_checkpoint_registry",
    "make_manifest",
    "register_checkpoint",
    "save_checkpoint_registry",
    "save_manifest",
]
