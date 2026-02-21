"""
Tournament: Multi-round debate management with transcript logging.
"""
from dataclasses import dataclass, field
from typing import Optional, List, Union
import json
from datetime import datetime

from .dynamic_round import DynamicDebateRound, DynamicRoundResult
from ..models import Debater, BaseJudge
from ..economy import TokenLedger, BettingManager, TokenDistributor
from ..logs import create_transcript, DebateTranscript


@dataclass
class EconomyParams:
    num_rounds: int = 5
    max_iterations: int = 10
    initial_balance: float = 100.0
    max_debt: float = 50.0
    tokens_per_round: float = 20.0
    betting_fee: float = 0.05
    min_bet: float = 5.0


@dataclass
class TournamentResult:
    config: "EconomyParams"
    rounds: List[DynamicRoundResult]
    final_balances: dict[str, float]
    winner: Optional[str]
    started_at: str
    ended_at: str
    eliminated: Optional[str] = None  # If someone went bankrupt
    transcript: Optional[DebateTranscript] = None


class Tournament:
    """
    Runs a multi-round debate tournament using DynamicDebateRound.
    """
    
    def __init__(
        self,
        debater_a: Debater,
        debater_b: Debater,
        judge: BaseJudge,
        topics: List[str],
        config: Optional[EconomyParams] = None,
        enable_transcript: bool = True,
        observers: Optional[List] = None,
        split_pot_enabled: bool = False,
        initial_pot_amount: float = 40.0,
    ):
        self.debater_a = debater_a
        self.debater_b = debater_b
        self.judge = judge
        self.topics = topics
        self.config = config or EconomyParams()
        self.enable_transcript = enable_transcript
        self.observers = observers or []
        self.split_pot_enabled = split_pot_enabled
        self.initial_pot_amount = initial_pot_amount
        
        # Initialize economy
        self.ledger = TokenLedger(
            self.config.initial_balance,
            self.config.max_debt,
        )
        self.betting = BettingManager(
            self.config.betting_fee,
            self.config.min_bet,
        )
        self.distributor = TokenDistributor(
            self.config.tokens_per_round,
        )
        
        # Register debaters
        self.ledger.register(debater_a.name)
        self.ledger.register(debater_b.name)
        
        self._results: List[DynamicRoundResult] = []
        self._transcript: Optional[DebateTranscript] = None
        self._eliminated: Optional[str] = None
    
    def run(self) -> TournamentResult:
        """Run the full tournament."""
        started_at = datetime.now().isoformat()
        
        # Create transcript
        if self.enable_transcript:
            self._transcript = create_transcript({
                "num_rounds": self.config.num_rounds,
                "initial_balance": self.config.initial_balance,
                "max_debt": self.config.max_debt,
                "tokens_per_round": self.config.tokens_per_round,
                "debater_a": self.debater_a.name,
                "debater_b": self.debater_b.name,
                "judge": self.judge.name,
            })
        
        # Load models
        self.debater_a.load_model()
        self.debater_b.load_model()
        self.judge.load_model()
        
        try:
            for round_id in range(1, self.config.num_rounds + 1):
                topic = self.topics[(round_id - 1) % len(self.topics)]
                
                print(f"\n=== Round {round_id}/{self.config.num_rounds}: {topic[:50]}... ===")
                
                # Check bankruptcy before starting round
                bal_a = self.ledger.balance(self.debater_a.name)
                bal_b = self.ledger.balance(self.debater_b.name)
                if bal_a <= 0:
                    print(f"  [ELIMINATED] {self.debater_a.name} is bankrupt!")
                    self._eliminated = self.debater_a.name
                    break
                if bal_b <= 0:
                    print(f"  [ELIMINATED] {self.debater_b.name} is bankrupt!")
                    self._eliminated = self.debater_b.name
                    break
                
                # Create round transcript
                round_transcript = None
                if self._transcript:
                    round_transcript = self._transcript.new_round(round_id, topic)
                
                debate_round = DynamicDebateRound(
                    self.debater_a,
                    self.debater_b,
                    self.judge,
                    self.ledger,
                    self.betting,
                    self.distributor,
                    max_iterations=self.config.max_iterations,
                    observers=self.observers,
                    split_pot_enabled=self.split_pot_enabled,
                    initial_pot_amount=self.initial_pot_amount,
                )
                
                result = debate_round.run(topic, round_id, transcript=round_transcript)
                self._results.append(result)
                
                # Print round summary
                print(f"  Confidence: A={result.final_judgment.confidence_a:.2f}, B={result.final_judgment.confidence_b:.2f}")
                print(f"  Tokens: A={result.tokens_awarded_a:.1f}, B={result.tokens_awarded_b:.1f}")
                print(f"  Iterations: {result.iterations_completed}")
                print(f"  Balances: A={self.ledger.balance(self.debater_a.name):.1f}, "
                      f"B={self.ledger.balance(self.debater_b.name):.1f}")
                
                # --- ROUND CHECKPOINT ---
                # Print human-readable narrative from observers if available
                if result.observation_reports:
                    print(f"  --- Round {round_id} Checkpoint ---")
                    for report in result.observation_reports:
                        # Print health warnings immediately
                        if report.observer_name == "health_check" and "WARNING" in report.narrative:
                            print(f"  {report.narrative}")
                        # Print general summary
                        elif report.observer_name == "MetricsObserver":
                            print(f"  Summary: {report.narrative}")
                    print(f"  -------------------------")
        
        finally:
            # Unload models
            self.debater_a.unload_model()
            self.debater_b.unload_model()
            self.judge.unload_model()
        
        ended_at = datetime.now().isoformat()
        
        # Determine winner
        bal_a = self.ledger.balance(self.debater_a.name)
        bal_b = self.ledger.balance(self.debater_b.name)
        if bal_a > bal_b:
            winner = self.debater_a.name
        elif bal_b > bal_a:
            winner = self.debater_b.name
        else:
            winner = None  # Tie
        
        # Finalize transcript
        if self._transcript:
            self._transcript.finalize(winner, {
                self.debater_a.name: bal_a,
                self.debater_b.name: bal_b,
            })
        
        return TournamentResult(
            config=self.config,
            rounds=self._results,
            final_balances={
                self.debater_a.name: bal_a,
                self.debater_b.name: bal_b,
            },
            winner=winner,
            started_at=started_at,
            ended_at=ended_at,
            eliminated=self._eliminated,
            transcript=self._transcript,
        )
    
    def save_results(self, path: str):
        """Save tournament results to JSON."""
        # Save ledger
        ledger_path = path.replace(".json", "_ledger.json")
        self.ledger.save(ledger_path)
        
        # Save transcript
        if self._transcript:
            transcript_json = path.replace(".json", "_transcript.json")
            transcript_md = path.replace(".json", "_transcript.md")
            self._transcript.save(transcript_json)
            self._transcript.save_markdown(transcript_md)
            print(f"Transcript saved to {transcript_md}")
        
        # Save summary
        summary = {
            "config": {
                "num_rounds": self.config.num_rounds,
                "initial_balance": self.config.initial_balance,
                "max_debt": self.config.max_debt,
            },
            "rounds": [
                {
                    "round_id": r.round_id,
                    "topic": r.topic,
                    "confidence_a": r.judgment.confidence_a,
                    "confidence_b": r.judgment.confidence_b,
                    "tokens_a": r.tokens_awarded_a,
                    "tokens_b": r.tokens_awarded_b,
                    "bets": len(getattr(r, 'all_bets', getattr(r, 'bets_placed', []))),
                }
                for r in self._results
            ],
            "final_balances": self.ledger.summary()["balances"],
        }
        with open(path, "w") as f:
            json.dump(summary, f, indent=2)
