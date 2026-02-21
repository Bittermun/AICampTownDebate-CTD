"""
Judge Factory: Creates judge instances from configuration.
"""
from typing import List, Union
from .judge import BaseJudge, LLMJudge, EnsembleJudge, ConsensusJudge, JudgeConfig


class JudgeFactory:
    """
    Factory class to construct judges based on simplified configurations.
    """
    
    @staticmethod
    def create_simple(model_path: str, name: str = "Judge") -> LLMJudge:
        """Create a single LLM judge."""
        return LLMJudge(JudgeConfig(model_path=model_path, name=name))

    @staticmethod
    def create_ensemble(model_paths: List[str], name: str = "EnsembleJudge") -> EnsembleJudge:
        """Create an ensemble judge from multiple models."""
        judges = [
            LLMJudge(JudgeConfig(model_path=path, name=f"SubJudge_{i}"))
            for i, path in enumerate(model_paths)
        ]
        return EnsembleJudge(judges, name=name)

    @staticmethod
    def create_consensus(
        sub_model_paths: List[str], 
        instructor_model_path: str, 
        name: str = "ConsensusJudge"
    ) -> ConsensusJudge:
        """
        Create a consensus judge with multiple sub-judges and an instructor.
        """
        judges = [
            LLMJudge(JudgeConfig(model_path=path, name=f"SubJudge_{i}"))
            for i, path in enumerate(sub_model_paths)
        ]
        instructor = LLMJudge(JudgeConfig(model_path=instructor_model_path, name="Instructor"))
        return ConsensusJudge(judges, instructor, name=name)
