"""
Betting: Handles bet placement and resolution.
"""
from dataclasses import dataclass
from typing import Optional
from enum import Enum


class BetStatus(Enum):
    PENDING = "pending"
    WON = "won"
    LOST = "lost"
    CANCELLED = "cancelled"


@dataclass
class Bet:
    bet_id: str
    bettor_id: str
    amount: float
    round_id: int
    status: BetStatus = BetStatus.PENDING
    payout: float = 0.0
    fee_paid: float = 0.0  # Actual fee burned (supports scaling fees)


class BettingManager:
    """
    Manages bet placement, fees, and resolution.
    """
    
    def __init__(self, fee_rate: float = 0.05, min_bet: float = 5.0):
        self.fee_rate = fee_rate  # 5% fee on bets
        self.min_bet = min_bet
        self._bets: list[Bet] = []
        self._bet_counter = 0
    
    def place_bet(
        self,
        bettor_id: str,
        amount: float,
        round_id: int,
        ledger,  # TokenLedger
        custom_fee_rate: Optional[float] = None,
    ) -> Optional[Bet]:
        """
        Place a bet. Deducts amount + fee from bettor.
        Returns Bet if successful, None if cannot afford.
        """
        if amount < self.min_bet:
            return None
        
        fee_rate = custom_fee_rate if custom_fee_rate is not None else self.fee_rate
        fee = amount * fee_rate
        total_cost = amount + fee
        
        # Check if can afford
        if not ledger.can_afford(bettor_id, total_cost):
            return None
        
        # Deduct stake
        ledger.deduct(bettor_id, amount, "bet_stake", round_id)
        # Deduct fee (burned)
        ledger.deduct(bettor_id, fee, "bet_fee", round_id)
        
        # Create bet
        self._bet_counter += 1
        bet = Bet(
            bet_id=f"BET-{self._bet_counter:04d}",
            bettor_id=bettor_id,
            amount=amount,
            round_id=round_id,
            fee_paid=fee,  # Track actual fee for scaling fee support
        )
        self._bets.append(bet)
        return bet
    
    def resolve_bet(
        self,
        bet: Bet,
        won: bool,
        multiplier: float,
        ledger,
    ):
        """
        Resolve a bet. If won, awards stake * multiplier.
        """
        if bet.status != BetStatus.PENDING:
            return
        
        if won:
            bet.status = BetStatus.WON
            bet.payout = bet.amount * multiplier
            ledger.award(
                bet.bettor_id,
                bet.payout,
                f"bet_won:{bet.bet_id}",
                bet.round_id,
            )
        else:
            bet.status = BetStatus.LOST
            bet.payout = 0.0
            # Stake already deducted, nothing more to do
    
    def get_pending_bets(self, round_id: Optional[int] = None) -> list[Bet]:
        """Get all pending bets, optionally filtered by round."""
        bets = [b for b in self._bets if b.status == BetStatus.PENDING]
        if round_id is not None:
            bets = [b for b in bets if b.round_id == round_id]
        return bets
    
    def total_fees_collected(self) -> float:
        """Total fees burned across all bets (supports scaling fees)."""
        return sum(b.fee_paid for b in self._bets)
