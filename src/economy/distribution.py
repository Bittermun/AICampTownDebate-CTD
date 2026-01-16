"""
Distribution: Converts judge confidence into token awards.
"""
from dataclasses import dataclass


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
    
    def __init__(self, tokens_per_round: float = 20.0):
        self.tokens_per_round = tokens_per_round
    
    def distribute_linear(
        self,
        agent_a_id: str,
        agent_b_id: str,
        confidence_a: float,
        confidence_b: float,
        round_id: int,
        ledger,
    ) -> DistributionResult:
        """
        Linear distribution: tokens proportional to confidence.
        If confidence_a = 0.7, agent A gets 70% of tokens.
        """
        total = confidence_a + confidence_b
        if total == 0:
            # Edge case: both zero confidence
            tokens_a = self.tokens_per_round / 2
            tokens_b = self.tokens_per_round / 2
        else:
            tokens_a = self.tokens_per_round * (confidence_a / total)
            tokens_b = self.tokens_per_round * (confidence_b / total)
        
        ledger.award(agent_a_id, tokens_a, "round_award", round_id)
        ledger.award(agent_b_id, tokens_b, "round_award", round_id)
        
        return DistributionResult(
            agent_a_id=agent_a_id,
            agent_b_id=agent_b_id,
            tokens_a=tokens_a,
            tokens_b=tokens_b,
            round_id=round_id,
        )
    
    def distribute_winner_takes_more(
        self,
        agent_a_id: str,
        agent_b_id: str,
        confidence_a: float,
        confidence_b: float,
        round_id: int,
        ledger,
        winner_bonus: float = 0.2,
    ) -> DistributionResult:
        """
        Winner-takes-more: Linear + bonus for winner.
        Creates stronger selection pressure.
        """
        total = confidence_a + confidence_b
        if total == 0:
            tokens_a = self.tokens_per_round / 2
            tokens_b = self.tokens_per_round / 2
        else:
            base_a = self.tokens_per_round * (confidence_a / total)
            base_b = self.tokens_per_round * (confidence_b / total)
            
            # Bonus to winner
            bonus = self.tokens_per_round * winner_bonus
            if confidence_a > confidence_b:
                tokens_a = base_a + bonus
                tokens_b = base_b
            elif confidence_b > confidence_a:
                tokens_a = base_a
                tokens_b = base_b + bonus
            else:
                tokens_a = base_a
                tokens_b = base_b
        
        ledger.award(agent_a_id, tokens_a, "round_award", round_id)
        ledger.award(agent_b_id, tokens_b, "round_award", round_id)
        
        return DistributionResult(
            agent_a_id=agent_a_id,
            agent_b_id=agent_b_id,
            tokens_a=tokens_a,
            tokens_b=tokens_b,
            round_id=round_id,
        )
