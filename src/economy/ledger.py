"""
Token Ledger: Tracks balances, debt, and transaction history.
"""
from dataclasses import dataclass
from typing import Optional
from datetime import datetime
import json
import math


@dataclass
class Transaction:
    timestamp: str
    from_id: Optional[str]  # None = mint/system
    to_id: Optional[str]    # None = burn/fee
    amount: float
    reason: str
    round_id: int


class TokenLedger:
    """
    Central ledger for the token economy.
    Tracks balances, debt, and all transactions.
    """
    
    def __init__(self, initial_balance: float = 200.0, max_debt: float = 50.0):
        self.initial_balance = initial_balance
        self.max_debt = max_debt
        self._balances: dict[str, float] = {}
        self._transactions: list[Transaction] = []
    
    def register(self, agent_id: str):
        """Register a new agent with initial balance."""
        if agent_id in self._balances:
            raise ValueError(f"Agent {agent_id} already registered")
        self._balances[agent_id] = self.initial_balance
        self._record(None, agent_id, self.initial_balance, "initial_balance", 0)
    
    def balance(self, agent_id: str) -> float:
        """Get current balance (can be negative = debt)."""
        return self._balances.get(agent_id, 0.0)
    
    def debt(self, agent_id: str) -> float:
        """Get current debt (0 if positive balance)."""
        bal = self.balance(agent_id)
        return abs(bal) if bal < 0 else 0.0
    
    def can_afford(self, agent_id: str, amount: float) -> bool:
        """Check if agent can afford amount (considering max debt)."""
        if not math.isfinite(amount):
            return False
        if amount < 0:
            return False
        projected = self.balance(agent_id) - amount
        return projected >= -self.max_debt
    
    def transfer(
        self,
        from_id: str,
        to_id: str,
        amount: float,
        reason: str,
        round_id: int,
    ) -> bool:
        """Transfer tokens between agents. Returns success."""
        if amount <= 0:
            return False
        if not self.can_afford(from_id, amount):
            return False
        
        self._balances[from_id] -= amount
        self._balances[to_id] = self._balances.get(to_id, 0) + amount
        self._record(from_id, to_id, amount, reason, round_id)
        return True
    
    def award(self, agent_id: str, amount: float, reason: str, round_id: int):
        """Award tokens from system (minting)."""
        if amount <= 0:
            return
        self._balances[agent_id] = self._balances.get(agent_id, 0) + amount
        self._record(None, agent_id, amount, reason, round_id)
    
    def deduct(self, agent_id: str, amount: float, reason: str, round_id: int) -> bool:
        """Deduct tokens (burn/fee). Returns success."""
        if not math.isfinite(amount) or amount <= 0:
            return False
        if not self.can_afford(agent_id, amount):
            return False
        self._balances[agent_id] -= amount
        self._record(agent_id, None, amount, reason, round_id)
        return True
    
    def _record(
        self,
        from_id: Optional[str],
        to_id: Optional[str],
        amount: float,
        reason: str,
        round_id: int,
    ):
        self._transactions.append(Transaction(
            timestamp=datetime.now().isoformat(),
            from_id=from_id,
            to_id=to_id,
            amount=amount,
            reason=reason,
            round_id=round_id,
        ))
    
    def get_history(self, agent_id: Optional[str] = None) -> list[Transaction]:
        """Get transaction history, optionally filtered by agent."""
        if agent_id is None:
            return self._transactions.copy()
        return [
            t for t in self._transactions
            if t.from_id == agent_id or t.to_id == agent_id
        ]
    
    def summary(self) -> dict:
        """Get summary of all balances."""
        return {
            "balances": self._balances.copy(),
            "total_supply": sum(self._balances.values()),
            "total_transactions": len(self._transactions),
        }
    
    def save(self, path: str):
        """Save ledger to JSON file."""
        data = {
            "initial_balance": self.initial_balance,
            "max_debt": self.max_debt,
            "balances": self._balances,
            "transactions": [
                {
                    "timestamp": t.timestamp,
                    "from": t.from_id,
                    "to": t.to_id,
                    "amount": t.amount,
                    "reason": t.reason,
                    "round": t.round_id,
                }
                for t in self._transactions
            ],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
    
    @classmethod
    def load(cls, path: str) -> "TokenLedger":
        """Load ledger from JSON file."""
        with open(path) as f:
            data = json.load(f)
        ledger = cls(data["initial_balance"], data["max_debt"])
        ledger._balances = data["balances"]
        ledger._transactions = [
            Transaction(
                timestamp=t["timestamp"],
                from_id=t["from"],
                to_id=t["to"],
                amount=t["amount"],
                reason=t["reason"],
                round_id=t["round"],
            )
            for t in data["transactions"]
        ]
        return ledger
