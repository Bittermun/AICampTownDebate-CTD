# System Architecture

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      TOURNAMENT ARENA                        │
│  ┌─────────────┐                      ┌─────────────┐       │
│  │  Debater A  │◄────── Prompt ──────►│  Debater B  │       │
│  │   (7B Q4)   │                      │   (7B Q4)   │       │
│  └──────┬──────┘                      └──────┬──────┘       │
│         │                                    │              │
│         ▼                                    ▼              │
│  ┌─────────────────────────────────────────────────┐        │
│  │                 ARGUMENT POOL                    │        │
│  └─────────────────────────────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │              JUDGE PANEL (Amnesiac)             │        │
│  │    Judge 1      Judge 2      Judge 3            │        │
│  └─────────────────────────────────────────────────┘        │
│                          │                                  │
│                          ▼                                  │
│  ┌─────────────────────────────────────────────────┐        │
│  │                 TOKEN ECONOMY                    │        │
│  │   Balances │ Bets │ Debt │ Fees │ Distribution  │        │
│  └─────────────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────────────┘
```

## Components

### 1. Debaters
- **Model**: 7B quantized (Mistral, Qwen2, or similar)
- **Format**: GGUF 4-bit for llama.cpp
- **Memory**: Persistent across rounds (token balance, strategy)
- **Count**: 2 per debate (expandable to tournament)

### 2. Judges
- **Model**: Same or smaller than debaters
- **Memory**: Amnesiac (reset each round)
- **Count**: 1-3 per debate (odd number for tiebreak)
- **Output**: Confidence score per argument (0.0 - 1.0)

### 3. Token Economy
```python
class TokenLedger:
    balances: dict[str, float]    # model_id → balance
    debts: dict[str, float]       # model_id → debt
    bets: list[Bet]               # pending bets
    
class Bet:
    model_id: str
    amount: float
    target: str                   # what they're betting against
    round_id: int
```

### 4. Tournament Manager
- Swiss-style pairing
- ELO-like tier movement
- Round scheduling

## Data Flow (Single Round)

```
1. PROMPT → Both debaters (parallel)
2. Debaters → Initial arguments
3. Arguments → Judges → Confidence scores
4. Confidence → Token distribution (proportional)
5. Debaters decide: bet or pass?
6. If bet: counter-argument phase
7. Final judging → bet resolution
8. Update balances, record to log
```

## File Structure

```
src/
├── config_loader.py       # YAML tournament configuration parser
├── models/
│   ├── debater.py         # LLM wrapper for debate + deliberation
│   ├── judge.py           # LLMJudge, EnsembleJudge, ConsensusJudge
│   ├── judge_factory.py   # Factory for building judge configurations
│   ├── ollama_backend.py  # Ollama API wrapper
│   ├── protocols.py       # Backend/Judge interface contracts
│   └── response_models.py # Pydantic models for LLM responses
├── economy/
│   ├── ledger.py          # Token tracking
│   ├── betting.py         # Bet mechanics + scaling fees
│   └── distribution.py    # Confidence → token distribution
├── arena/
│   ├── round.py           # Phase-based single round logic
│   ├── dynamic_round.py   # Iterative betting until mutual PASS
│   ├── observers.py       # MetricsObserver, ScribeObserver
│   └── tournament.py      # Multi-round management
└── logs/
    └── transcript.py      # JSON + Markdown transcript export
```

## Configuration

```yaml
# configs/tournament_config.yaml
models:
  judge_type: consensus     # "single", "ensemble", or "consensus"
  instructor_model: "qwen2.5:7b"
  debaters:
    - name: "Alpha"
      model: "qwen2.5:7b"
    - name: "Beta"
      model: "llama3:8b"
  judges:
    - model: "qwen2.5:1.5b"
      weight: 1.0

economy:
  initial_balance: 200
  max_debt: 50
  split_pot_enabled: true
  initial_pot_amount: 40

rounds:
  max_iterations: 10
  topic: "Should AI be regulated?"
```

## Open Design Questions

1. **Token distribution formula**: Linear with confidence? Exponential?
2. **Debt interest**: Compound per round? Flat penalty?
3. **Bankruptcy**: Reset to zero? Partial reset? Elimination?
4. **Truth-focus triggers**: Random? Every N rounds? On low confidence?
