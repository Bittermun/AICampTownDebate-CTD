# Economic Parameter Analysis

## What's Real Math vs. What's a Knob

| Parameter | Current Value | Source | Grounded? |
|---|---|---|---|
| Initial balance | 200 | Design choice | ❌ Arbitrary |
| Pot per round | 100 | Design choice | ❌ Arbitrary |
| Max debt | 50 | Design choice | ❌ Arbitrary |
| Fee rate | 5% × iteration | Design choice | ⚠️ Shape is deliberate (escalation), rate is arbitrary |
| Fee cap | 50% | Design choice | ❌ Arbitrary |
| Token cost ratio | 20:1 (economic:LLM) | Design choice | ❌ Arbitrary |
| Judge dimension weights | 40/30/30 | Design choice | ❌ Arbitrary |

**Honest answer: nothing here comes from a formula yet.** These were tuned until behavior "looked right." That doesn't mean they're wrong — but it means we can't explain *why* they should be these values.

---

## Formulas That Actually Apply

### 1. Expected Value Per Bet

```
EV = (win_prob × payout) - (lose_prob × stake) - fee

If:  win_prob = 0.5 (symmetric models)
     stake   = 20
     payout  = 20 (winner gets their stake back + opponent's)
     fee     = 5% × iteration × stake

Iteration 1: EV = (0.5 × 20) - (0.5 × 20) - 1.0 = -1.0
Iteration 3: EV = (0.5 × 20) - (0.5 × 20) - 3.0 = -3.0
Iteration 5: EV = (0.5 × 20) - (0.5 × 20) - 5.0 = -5.0
```

**Key insight**: For equally-matched models, EVERY bet has negative expected value because of fees. This means **rational behavior under symmetry is to never bet**. The only reason TO bet is if you believe you have an *edge* — your argument is genuinely better than the opponent's.

This is actually correct incentive design. Fees act like the rake in poker — they punish random betting and reward informed betting.

### 2. Kelly Criterion (Optimal Bet Size)

The Kelly formula says bet this fraction of your bankroll:

```
f* = (p(b+1) - 1) / b

Where:
  p = your probability of winning (estimated)
  b = odds ratio (payout / stake, here = 1 after fees)
  
After fees at iteration 3 (15% fee):
  Effective b = 0.85 (you win 85% of opponent's stake)
  
  If p = 0.6 (you think you're 60% likely to win):
  f* = (0.6 × 1.85 - 1) / 0.85 = 0.13 → bet 13% of balance
  
  At balance = 150: optimal bet = ~19.5 tokens
  At balance = 80:  optimal bet = ~10.4 tokens
```

**Key insight**: Kelly naturally tells the model to bet LESS as balance decreases. If your models bet the same amount regardless of balance, they're being suboptimal — and that's measurable.

### 3. Survival Threshold

```
Minimum viable balance = generation_cost + minimum_bet
                       ≈ 20 (generation) + 5 (min bet) = 25 tokens

Rounds until bankruptcy from initial 200, losing every round:
  Avg cost per round ≈ 30 (gen) + 20 (bet lost) + 3 (avg fee) = 53
  200 / 53 ≈ 3.8 rounds
```

**A model that never wins goes bankrupt in ~4 rounds.** With max debt of 50: ~5 rounds. Is that enough runway for adaptation? Maybe not — the model gets barely 4 chances to learn before extinction.

---

## What This Tells You

### Parameters that seem reasonable:
- **Fee escalation** (5% × iteration): Creates natural round termination. Mathematically sound.
- **Negative EV for random betting**: Only informed bets are profitable. Correct incentive.

### Parameters that might be problematic:
- **Survival runway (~4-5 rounds)**: Very short. A model barely has time to adapt before going bankrupt. Consider: lower fees, higher initial balance, or a "welfare floor" that prevents total elimination.
- **Pot size (100) vs. generation cost (~30)**: The pot is generous relative to costs. This means a single round win can fund 3+ rounds of generation. This might make "win one big, coast on PASS" a dominant strategy.
- **Token cost ratio (20:1)**: This is the least grounded number. It converts LLM tokens (which vary by model and prompt) into economic tokens. If you change models, this ratio silently breaks.

---

## The Optimization Question

Could you optimize these parameters automatically? Yes, in theory:

```
for each parameter_combination:
    run N tournaments
    measure: strategy_diversity, round_survival, bet_quality
    score = diversity × 0.4 + survival × 0.3 + bet_quality × 0.3
    
select parameters that maximize score
```

But this requires defining what "good tournament behavior" looks like — which brings you back to the same question. The math can check *consistency* (do outcomes match predictions?), but it can't tell you what outcomes you *want*.

### My Recommendation

Don't optimize parameters blindly. Instead:

1. Use the Kelly/EV formulas above to set **bounds** (fee rate that keeps EV negative for random betting but positive for 60%+ win rate)
2. Check the survival runway (is 4-5 rounds enough?)
3. Run the stress tests from earlier to verify the system matches these predictions
4. THEN scale up to tournaments
