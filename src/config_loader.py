"""
Config Loader: Load and validate tournament configuration from YAML files.
"""
import yaml
from dataclasses import dataclass, field
from typing import List, Optional
from pathlib import Path


@dataclass
class DebaterSpec:
    """Specification for a single debater."""
    name: str
    model: str
    system_prompt: Optional[str] = None


@dataclass
class JudgeSpec:
    """Specification for a judge (supports ensemble weighting)."""
    model: str
    weight: float = 1.0
    name: Optional[str] = None


@dataclass
class EconomyConfig:
    """Economic parameters for the tournament."""
    initial_balance: float = 200.0
    max_debt: float = 50.0
    tokens_per_round: float = 100.0
    split_pot_enabled: bool = False
    initial_pot_amount: float = 40.0


@dataclass
class RoundConfig:
    """Round execution parameters."""
    max_iterations: int = 10
    topic: str = "Should AI development be regulated by governments?"


@dataclass
class TournamentConfig:
    """Complete tournament configuration."""
    debaters: List[DebaterSpec] = field(default_factory=list)
    judges: List[JudgeSpec] = field(default_factory=list)
    economy: EconomyConfig = field(default_factory=EconomyConfig)
    rounds: RoundConfig = field(default_factory=RoundConfig)
    judge_type: str = "single"  # "single", "ensemble", or "consensus"
    instructor_model: Optional[str] = None  # For consensus judge
    randomize_argument_order: bool = False  # Mitigate positional bias in judge


def load_config(path: str) -> TournamentConfig:
    """Load tournament configuration from YAML file."""
    with open(path, 'r') as f:
        data = yaml.safe_load(f)
    
    # Parse debaters
    debaters = []
    for d in data.get('models', {}).get('debaters', []):
        debaters.append(DebaterSpec(
            name=d['name'],
            model=d['model'],
            system_prompt=d.get('system_prompt'),
        ))
    
    # Parse judges
    judges = []
    for j in data.get('models', {}).get('judges', []):
        judges.append(JudgeSpec(
            model=j['model'],
            weight=j.get('weight', 1.0),
            name=j.get('name'),
        ))
    
    # Parse economy
    eco_data = data.get('economy', {})
    economy = EconomyConfig(
        initial_balance=eco_data.get('initial_balance', 200.0),
        max_debt=eco_data.get('max_debt', 50.0),
        tokens_per_round=eco_data.get('tokens_per_round', 100.0),
        split_pot_enabled=eco_data.get('split_pot_enabled', False),
        initial_pot_amount=eco_data.get('initial_pot_amount', 40.0),
    )
    
    # Parse rounds
    round_data = data.get('rounds', {})
    rounds = RoundConfig(
        max_iterations=round_data.get('max_iterations', 10),
        topic=round_data.get('topic', "Should AI development be regulated by governments?"),
    )
    
    # Parse judge configuration
    models_data = data.get('models', {})
    judge_type = models_data.get('judge_type', 'single')
    instructor_model = models_data.get('instructor_model')
    randomize_argument_order = models_data.get('randomize_argument_order', False)
    
    return TournamentConfig(
        debaters=debaters,
        judges=judges,
        economy=economy,
        rounds=rounds,
        judge_type=judge_type,
        instructor_model=instructor_model,
        randomize_argument_order=randomize_argument_order,
    )


def get_default_config() -> TournamentConfig:
    """Return default configuration (used when no config file provided)."""
    return TournamentConfig(
        debaters=[
            DebaterSpec(name="Alpha", model="qwen2.5:1.5b"),
            DebaterSpec(name="Beta", model="qwen2.5:1.5b"),
        ],
        judges=[
            JudgeSpec(model="qwen2.5:1.5b", weight=1.0),
        ],
        economy=EconomyConfig(),
        rounds=RoundConfig(),
    )
