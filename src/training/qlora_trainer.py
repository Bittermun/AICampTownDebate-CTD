"""QLoRA trainer implementing TrainerInterface.

Requires optional dependencies: torch, transformers, peft, trl.
Install with: pip install -r requirements-training.txt
"""
from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .trainer_interface import TrainingRunResult, TrainingStageResult

logger = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _check_training_deps() -> None:
    """Raise ImportError with helpful message if training deps are missing."""
    missing = []
    for pkg in ["torch", "transformers", "peft", "trl"]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pkg)
    if missing:
        raise ImportError(
            f"Training requires: {', '.join(missing)}. "
            f"Install with: pip install -r requirements-training.txt"
        )


@dataclass
class QLoRAConfig:
    """Configuration for QLoRA fine-tuning."""
    # Model
    base_model: str = "Qwen/Qwen2.5-1.5B-Instruct"

    # QLoRA params
    lora_r: int = 16
    lora_alpha: int = 32
    lora_dropout: float = 0.05
    target_modules: List[str] = field(
        default_factory=lambda: ["q_proj", "k_proj", "v_proj", "o_proj"]
    )

    # Training params
    num_epochs: int = 3
    batch_size: int = 4
    gradient_accumulation_steps: int = 4
    learning_rate: float = 2e-4
    warmup_ratio: float = 0.03
    max_seq_length: int = 1024
    weight_decay: float = 0.01

    # DPO params (for preference stage)
    dpo_beta: float = 0.1

    # Quantization
    load_in_4bit: bool = True
    bnb_4bit_compute_dtype: str = "float16"
    bnb_4bit_quant_type: str = "nf4"

    # Output
    save_steps: int = 50
    logging_steps: int = 10

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "QLoRAConfig":
        known = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in known})

    def to_dict(self) -> Dict[str, Any]:
        from dataclasses import asdict
        return asdict(self)


def _load_jsonl(path: str) -> List[Dict[str, Any]]:
    """Load a JSONL file into a list of dicts."""
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


class QLoRATrainer:
    """QLoRA fine-tuning trainer for debate traces.

    Implements TrainerInterface protocol.

    Two-stage pipeline:
    1. SFT stage: supervised fine-tuning on winning debate traces
    2. Preference stage: DPO on chosen/rejected decision pairs
    """

    name = "qlora_trainer"

    def __init__(self, config: Optional[QLoRAConfig] = None):
        self.config = config or QLoRAConfig()

    def run(
        self,
        *,
        sft_dataset_path: Optional[str] = None,
        preference_dataset_path: Optional[str] = None,
        base_checkpoint_path: Optional[str] = None,
        output_dir: str,
        config: Optional[Dict[str, Any]] = None,
    ) -> TrainingRunResult:
        _check_training_deps()

        if config:
            self.config = QLoRAConfig.from_dict(config)

        run_id = f"train_{uuid.uuid4().hex[:12]}"
        started = _now_iso()
        stages: List[TrainingStageResult] = []
        out_dir = Path(output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)

        current_checkpoint = base_checkpoint_path or self.config.base_model

        # Stage 1: SFT
        if sft_dataset_path:
            logger.info("Starting SFT stage from %s", sft_dataset_path)
            sft_output = str(out_dir / "sft_checkpoint")
            sft_result = self._run_sft(
                dataset_path=sft_dataset_path,
                base_model_or_checkpoint=current_checkpoint,
                output_dir=sft_output,
            )
            stages.append(sft_result)
            if sft_result.success and sft_result.checkpoint_path:
                current_checkpoint = sft_result.checkpoint_path

        # Stage 2: DPO preference learning
        if preference_dataset_path:
            logger.info("Starting DPO stage from %s", preference_dataset_path)
            dpo_output = str(out_dir / "dpo_checkpoint")
            dpo_result = self._run_dpo(
                dataset_path=preference_dataset_path,
                base_model_or_checkpoint=current_checkpoint,
                output_dir=dpo_output,
            )
            stages.append(dpo_result)

        return TrainingRunResult(
            run_id=run_id,
            trainer_name=self.name,
            started_at=started,
            finished_at=_now_iso(),
            stages=stages,
            metadata={
                "config": self.config.to_dict(),
                "base_checkpoint_path": base_checkpoint_path,
            },
        )

    def _run_sft(
        self,
        dataset_path: str,
        base_model_or_checkpoint: str,
        output_dir: str,
    ) -> TrainingStageResult:
        """Run SFT stage using TRL's SFTTrainer with QLoRA."""
        try:
            import torch
            from datasets import Dataset
            from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                BitsAndBytesConfig,
                TrainingArguments,
            )
            from trl import SFTTrainer

            records = _load_jsonl(dataset_path)
            if not records:
                return TrainingStageResult(
                    stage="sft", success=False,
                    notes=["No training examples found in dataset"],
                )

            # Format for SFT: prompt + response as single text
            texts = []
            for r in records:
                prompt = r.get("prompt", "")
                response = r.get("response", "")
                texts.append(f"### Instruction:\n{prompt}\n\n### Response:\n{response}")

            dataset = Dataset.from_dict({"text": texts})

            # Quantization config
            compute_dtype = getattr(torch, self.config.bnb_4bit_compute_dtype, torch.float16)
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=self.config.load_in_4bit,
                bnb_4bit_quant_type=self.config.bnb_4bit_quant_type,
                bnb_4bit_compute_dtype=compute_dtype,
                bnb_4bit_use_double_quant=True,
            )

            tokenizer = AutoTokenizer.from_pretrained(base_model_or_checkpoint)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            model = AutoModelForCausalLM.from_pretrained(
                base_model_or_checkpoint,
                quantization_config=bnb_config,
                device_map="auto",
                torch_dtype=compute_dtype,
            )
            model = prepare_model_for_kbit_training(model)

            lora_config = LoraConfig(
                r=self.config.lora_r,
                lora_alpha=self.config.lora_alpha,
                lora_dropout=self.config.lora_dropout,
                target_modules=self.config.target_modules,
                bias="none",
                task_type="CAUSAL_LM",
            )

            training_args = TrainingArguments(
                output_dir=output_dir,
                num_train_epochs=self.config.num_epochs,
                per_device_train_batch_size=self.config.batch_size,
                gradient_accumulation_steps=self.config.gradient_accumulation_steps,
                learning_rate=self.config.learning_rate,
                warmup_ratio=self.config.warmup_ratio,
                weight_decay=self.config.weight_decay,
                logging_steps=self.config.logging_steps,
                save_steps=self.config.save_steps,
                save_total_limit=2,
                fp16=compute_dtype == torch.float16,
                bf16=compute_dtype == torch.bfloat16,
                report_to="none",
                remove_unused_columns=False,
            )

            trainer = SFTTrainer(
                model=model,
                train_dataset=dataset,
                peft_config=lora_config,
                args=training_args,
                tokenizer=tokenizer,
                max_seq_length=self.config.max_seq_length,
            )

            train_result = trainer.train()
            trainer.save_model(output_dir)
            tokenizer.save_pretrained(output_dir)

            metrics = {
                "train_loss": train_result.training_loss,
                "examples_seen": float(len(records)),
                "train_steps": float(train_result.global_step),
            }

            return TrainingStageResult(
                stage="sft",
                success=True,
                checkpoint_path=output_dir,
                metrics=metrics,
                notes=[f"SFT completed on {len(records)} examples"],
            )

        except Exception as e:
            logger.exception("SFT stage failed")
            return TrainingStageResult(
                stage="sft", success=False,
                notes=[f"SFT failed: {e}"],
            )

    def _run_dpo(
        self,
        dataset_path: str,
        base_model_or_checkpoint: str,
        output_dir: str,
    ) -> TrainingStageResult:
        """Run DPO preference learning stage."""
        try:
            import torch
            from datasets import Dataset
            from peft import LoraConfig
            from transformers import (
                AutoModelForCausalLM,
                AutoTokenizer,
                BitsAndBytesConfig,
                TrainingArguments,
            )
            from trl import DPOTrainer

            records = _load_jsonl(dataset_path)
            if not records:
                return TrainingStageResult(
                    stage="preference", success=False,
                    notes=["No preference pairs found in dataset"],
                )

            # Format for DPO
            prompts = []
            chosen_responses = []
            rejected_responses = []
            for r in records:
                prompts.append(r.get("prompt", ""))
                chosen_responses.append(r.get("chosen", ""))
                rejected_responses.append(r.get("rejected", ""))

            dataset = Dataset.from_dict({
                "prompt": prompts,
                "chosen": chosen_responses,
                "rejected": rejected_responses,
            })

            compute_dtype = getattr(torch, self.config.bnb_4bit_compute_dtype, torch.float16)
            bnb_config = BitsAndBytesConfig(
                load_in_4bit=self.config.load_in_4bit,
                bnb_4bit_quant_type=self.config.bnb_4bit_quant_type,
                bnb_4bit_compute_dtype=compute_dtype,
                bnb_4bit_use_double_quant=True,
            )

            tokenizer = AutoTokenizer.from_pretrained(base_model_or_checkpoint)
            if tokenizer.pad_token is None:
                tokenizer.pad_token = tokenizer.eos_token

            model = AutoModelForCausalLM.from_pretrained(
                base_model_or_checkpoint,
                quantization_config=bnb_config,
                device_map="auto",
                torch_dtype=compute_dtype,
            )

            # For DPO we need a reference model — use the same base loaded separately
            ref_model = AutoModelForCausalLM.from_pretrained(
                base_model_or_checkpoint,
                quantization_config=bnb_config,
                device_map="auto",
                torch_dtype=compute_dtype,
            )

            lora_config = LoraConfig(
                r=self.config.lora_r,
                lora_alpha=self.config.lora_alpha,
                lora_dropout=self.config.lora_dropout,
                target_modules=self.config.target_modules,
                bias="none",
                task_type="CAUSAL_LM",
            )

            training_args = TrainingArguments(
                output_dir=output_dir,
                num_train_epochs=self.config.num_epochs,
                per_device_train_batch_size=self.config.batch_size,
                gradient_accumulation_steps=self.config.gradient_accumulation_steps,
                learning_rate=self.config.learning_rate,
                warmup_ratio=self.config.warmup_ratio,
                weight_decay=self.config.weight_decay,
                logging_steps=self.config.logging_steps,
                save_steps=self.config.save_steps,
                save_total_limit=2,
                fp16=compute_dtype == torch.float16,
                bf16=compute_dtype == torch.bfloat16,
                report_to="none",
                remove_unused_columns=False,
            )

            trainer = DPOTrainer(
                model=model,
                ref_model=ref_model,
                train_dataset=dataset,
                peft_config=lora_config,
                args=training_args,
                tokenizer=tokenizer,
                beta=self.config.dpo_beta,
                max_length=self.config.max_seq_length,
            )

            train_result = trainer.train()
            trainer.save_model(output_dir)
            tokenizer.save_pretrained(output_dir)

            metrics = {
                "train_loss": train_result.training_loss,
                "pairs_seen": float(len(records)),
                "train_steps": float(train_result.global_step),
            }

            return TrainingStageResult(
                stage="preference",
                success=True,
                checkpoint_path=output_dir,
                metrics=metrics,
                notes=[f"DPO completed on {len(records)} pairs"],
            )

        except Exception as e:
            logger.exception("DPO stage failed")
            return TrainingStageResult(
                stage="preference", success=False,
                notes=[f"DPO failed: {e}"],
            )
