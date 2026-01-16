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
├── models/
│   ├── debater.py      # LLM wrapper for debate
│   └── judge.py        # LLM wrapper for judging
├── economy/
│   ├── ledger.py       # Token tracking
│   ├── betting.py      # Bet mechanics
│   └── distribution.py # Confidence → tokens
├── arena/
│   ├── round.py        # Single round logic
│   ├── tournament.py   # Multi-round management
│   └── pairing.py      # Swiss pairing
├── prompts/
│   ├── debate.txt      # Debater system prompt
│   ├── judge.txt       # Judge system prompt
│   └── topics/         # Debate topics
└── logs/
    ├── debates/        # Full transcripts
    └── economy/        # Token history
```

## Configuration

```yaml
# config.yaml
models:
  debater: "mistral-7b-instruct-v0.2.Q4_K_M.gguf"
  judge: "phi-3-mini-4k-instruct.Q4_K_M.gguf"
  
economy:
  initial_balance: 100
  max_debt: 50
  betting_fee: 0.05          # 5% of bet
  min_bet: 5
  
tournament:
  rounds: 5
  judges_per_debate: 1       # start simple
  
hardware:
  gpu_layers: 20             # adjust for 8GB VRAM
  context_size: 4096
```

## Open Design Questions

1. **Token distribution formula**: Linear with confidence? Exponential?
2. **Debt interest**: Compound per round? Flat penalty?
3. **Bankruptcy**: Reset to zero? Partial reset? Elimination?
4. **Truth-focus triggers**: Random? Every N rounds? On low confidence?
