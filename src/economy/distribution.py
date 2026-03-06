"""
Distribution: Converts judge confidence into token awards.
"""
from dataclasses import dataclass
import math


@dataclass
class DistributionResult:
    agent_a_id: str
    agent_b_id: str
    tokens_a: float
    tokens_b: float
    round_id: int

class TokenDistributor:
    """
    Converts judge confidence scores into token awards.
    """
    
    def __init__(self, tokens_per_round: float = 20.0, exponent: float = 2.0):
        self.tokens_per_round = tokens_per_round
        self.exponent = exponent
    
    def distribute_pot(
        self,
        agent_a_id: str,
        agent_b_id: str,
        confidence_a: float,
        confidence_b: float,
        round_id: int,
        ledger,
        extra_pot_tokens: float = 0.0,
    ) -> DistributionResult:
        """
        Pari-mutuel Pot Split: Total pot (Base Award + Extra) split by exponential confidence.
        """
        for name, value in (
            ("confidence_a", confidence_a),
            ("confidence_b", confidence_b),
            ("extra_pot_tokens", extra_pot_tokens),
        ):
            if not math.isfinite(value):
                raise ValueError(f"{name} must be finite (got {value})")
        if confidence_a < 0.0 or confidence_b < 0.0:
            raise ValueError(
                f"Confidences must be non-negative (got confidence_a={confidence_a}, confidence_b={confidence_b})"
            )

        total_pot = self.tokens_per_round + extra_pot_tokens
        if not math.isfinite(total_pot) or total_pot < 0.0:
            raise ValueError(f"total_pot must be finite and non-negative (got {total_pot})")
        total_conf = confidence_a + confidence_b

        if total_conf <= 0:
            tokens_a = total_pot / 2
            tokens_b = total_pot / 2
        else:
            conf_a_exp = confidence_a ** self.exponent
            conf_b_exp = confidence_b ** self.exponent
            total_exp = conf_a_exp + conf_b_exp
            
            if total_exp <= 0:
                tokens_a = total_pot / 2
                tokens_b = total_pot / 2
            else:
                tokens_a = total_pot * (conf_a_exp / total_exp)
                tokens_b = total_pot * (conf_b_exp / total_exp)
        
        # Invariant check: tokens awarded must equal tokens available (prevents leaks)
        assert abs(tokens_a + tokens_b - total_pot) < 0.01, \
            f"Token leak detected: awarded {tokens_a + tokens_b}, pot was {total_pot}"
        
        # Awards
        ledger.award(agent_a_id, tokens_a, "pot_split", round_id)
        ledger.award(agent_b_id, tokens_b, "pot_split", round_id)
        
        return DistributionResult(
            agent_a_id=agent_a_id,
            agent_b_id=agent_b_id,
            tokens_a=tokens_a,
            tokens_b=tokens_b,
            round_id=round_id,
        )

    def distribute_linear(
        self,
        agent_a_id: str,
        agent_b_id: str,
        confidence_a: float,
        confidence_b: float,
        round_id: int,
        ledger,
    ) -> DistributionResult:
        """Legacy linear split (no extra pot)."""
        return self.distribute_pot(agent_a_id, agent_b_id, confidence_a, confidence_b, round_id, ledger, extra_pot_tokens=0.0)
