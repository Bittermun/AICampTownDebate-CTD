"""Backward-compatible judge construction helpers."""

from __future__ import annotations

from typing import Iterable, Optional

from .judge import ConsensusJudge, EnsembleJudge, JudgeConfig, LLMJudge


class JudgeFactory:
    """Factory API kept for compatibility with older scripts/tests."""

    @staticmethod
    def create_simple(
        model_path: str,
        *,
        name: str = "Judge",
        system_prompt: Optional[str] = None,
        randomize_argument_order: bool = False,
        strict_runtime: bool = True,
    ) -> LLMJudge:
        return LLMJudge(
            JudgeConfig(
                model_path=model_path,
                name=name,
                system_prompt=system_prompt,
                randomize_argument_order=randomize_argument_order,
                strict_runtime=strict_runtime,
            )
        )

    @staticmethod
    def create_ensemble(
        model_paths: Iterable[str],
        *,
        name: str = "EnsembleJudge",
        strict_runtime: bool = True,
    ) -> EnsembleJudge:
        judges = [
            LLMJudge(
                JudgeConfig(
                    model_path=model_path,
                    name=f"{name}_Member_{idx + 1}",
                    strict_runtime=strict_runtime,
                )
            )
            for idx, model_path in enumerate(model_paths)
        ]
        return EnsembleJudge(judges=judges, name=name)

    @staticmethod
    def create_consensus(
        *,
        sub_model_paths: Iterable[str],
        instructor_model_path: str,
        name: str = "ConsensusJudge",
        strict_runtime: bool = True,
    ) -> ConsensusJudge:
        sub_judges = [
            LLMJudge(
                JudgeConfig(
                    model_path=model_path,
                    name=f"{name}_SubJudge_{idx + 1}",
                    strict_runtime=strict_runtime,
                )
            )
            for idx, model_path in enumerate(sub_model_paths)
        ]
        instructor = LLMJudge(
            JudgeConfig(
                model_path=instructor_model_path,
                name=f"{name}_Instructor",
                strict_runtime=strict_runtime,
            )
        )
        return ConsensusJudge(judges=sub_judges, instructor=instructor, name=name)
