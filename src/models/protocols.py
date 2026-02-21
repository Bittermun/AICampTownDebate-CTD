"""
Protocols: Explicit interface contracts for the Token-Debate system.
Uses typing.Protocol for structural subtyping (duck typing with type safety).
"""
from typing import Protocol, Optional, List
from dataclasses import dataclass


@dataclass
class GenerationResult:
    """Result from LLM generation."""
    text: str
    tokens_used: int


class LLMBackend(Protocol):
    """Contract for LLM backends (Ollama, llama.cpp, etc.)."""
    
    def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        max_tokens: int = 512,
        json_mode: bool = False,
    ) -> GenerationResult:
        """Generate text from the model."""
        ...
    
    def is_available(self) -> bool:
        """Check if the backend is available."""
        ...


class JudgeProtocol(Protocol):
    """Contract for judge implementations."""
    
    @property
    def name(self) -> str:
        """Unique identifier for the judge."""
        ...
    
    def load_model(self) -> None:
        """Load the underlying model(s)."""
        ...
    
    def evaluate(
        self,
        topic: str,
        argument_a: str,
        argument_b: str,
        round_id: int,
    ):  # Returns Judgment, but avoiding circular import
        """Evaluate two arguments and return a Judgment."""
        ...
    
    def reset(self) -> None:
        """Reset any internal state (amnesia)."""
        ...
    
    def unload_model(self) -> None:
        """Free model from memory."""
        ...


class DebaterProtocol(Protocol):
    """Contract for debater implementations."""
    
    @property
    def name(self) -> str:
        """Unique identifier for the debater."""
        ...
    
    def load_model(self) -> None:
        """Load the underlying model."""
        ...
    
    def generate_argument(
        self,
        topic: str,
        round_id: int,
        opponent_argument: Optional[str] = None,
        current_balance: Optional[float] = None,
        confidence_self: Optional[float] = None,
        confidence_opponent: Optional[float] = None,
    ):  # Returns Argument
        """Generate an argument on the topic."""
        ...
    
    def decide_bet(
        self,
        balance: float,
        opponent_argument: str,
        own_argument: str,
        confidence_self: float = 0.5,
        confidence_opponent: float = 0.5,
    ):  # Returns BetDecision
        """Decide whether to bet on a counter-argument or research."""
        ...
