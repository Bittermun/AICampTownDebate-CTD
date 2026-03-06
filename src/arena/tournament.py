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
    early_stop_reason: Optional[str] = None
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
        self._early_stop_reason: Optional[str] = None
    
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
                
                # Check early stopping conditions (SPRT & Bankruptcy)
                bal_a = self.ledger.balance(self.debater_a.name)
                bal_b = self.ledger.balance(self.debater_b.name)
                if bal_a <= 0:
                    print(f"  [EARLY STOP] {self.debater_a.name} is bankrupt!")
                    self._eliminated = self.debater_a.name
                    self._early_stop_reason = "bankruptcy"
                    break
                if bal_b <= 0:
                    print(f"  [EARLY STOP] {self.debater_b.name} is bankrupt!")
                    self._eliminated = self.debater_b.name
                    self._early_stop_reason = "bankruptcy"
                    break
                    
                # SPRT Unrecoverable Delta (if past midpoint and difference > 50 tokens)
                if round_id > self.config.num_rounds // 2:
                    diff = abs(bal_a - bal_b)
                    if diff >= 50.0:
                        loser = self.debater_b.name if bal_a > bal_b else self.debater_a.name
                        print(f"  [EARLY STOP] Unrecoverable delta ({diff:.1f} tokens). {loser} mathematically eliminated.")
                        self._eliminated = loser
                        self._early_stop_reason = "sprt_unrecoverable"
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
                
                # Record outcome into debater memory for cross-round learning
                if hasattr(self.debater_a, 'memory'):
                    self.debater_a.memory.record_outcome(
                        round_id=round_id,
                        topic=topic,
                        confidence_self=result.final_judgment.confidence_a,
                        confidence_opponent=result.final_judgment.confidence_b,
                        judgment_reasoning=result.final_judgment.reasoning,
                    )
                if hasattr(self.debater_b, 'memory'):
                    self.debater_b.memory.record_outcome(
                        round_id=round_id,
                        topic=topic,
                        confidence_self=result.final_judgment.confidence_b,
                        confidence_opponent=result.final_judgment.confidence_a,
                        judgment_reasoning=result.final_judgment.reasoning,
                    )
                
                # Print round summary
                # Per-round efficiency: confidence gained per token spent
                conf_gain_a = max(0, result.final_judgment.confidence_a - result.initial_judgment.confidence_a)
                conf_gain_b = max(0, result.final_judgment.confidence_b - result.initial_judgment.confidence_b)
                eff_a = conf_gain_a / max(1, result.gen_cost_a) if result.gen_cost_a > 0 else 0
                eff_b = conf_gain_b / max(1, result.gen_cost_b) if result.gen_cost_b > 0 else 0

                print(f"  Confidence: A={result.final_judgment.confidence_a:.2f}, B={result.final_judgment.confidence_b:.2f}")
                print(f"  Tokens: A={result.tokens_awarded_a:.1f}, B={result.tokens_awarded_b:.1f}")
                print(f"  Cost: A={result.gen_cost_a:.0f}, B={result.gen_cost_b:.0f} | Efficiency: A={eff_a:.4f}, B={eff_b:.4f}")
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
            early_stop_reason=self._early_stop_reason,
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
        def _round_bet_status_counts(round_result: DynamicRoundResult) -> dict[str, int]:
            counts = {"pending": 0, "won": 0, "lost": 0, "cancelled": 0}
            for bet in getattr(round_result, "all_bets", []):
                status = str(getattr(getattr(bet, "status", ""), "value", "")).lower()
                if status in counts:
                    counts[status] += 1
            return counts

        # Compute learning curve: efficiency per round for each debater
        learning_curve_a = []
        learning_curve_b = []
        for r in self._results:
            conf_gain_a = max(0, r.final_judgment.confidence_a - r.initial_judgment.confidence_a)
            conf_gain_b = max(0, r.final_judgment.confidence_b - r.initial_judgment.confidence_b)
            cost_a = getattr(r, 'gen_cost_a', 0)
            cost_b = getattr(r, 'gen_cost_b', 0)
            learning_curve_a.append(conf_gain_a / max(1, cost_a) if cost_a > 0 else 0)
            learning_curve_b.append(conf_gain_b / max(1, cost_b) if cost_b > 0 else 0)

        # Early vs late half comparison (does efficiency improve?)
        half = max(1, len(learning_curve_a) // 2)
        early_eff_a = sum(learning_curve_a[:half]) / half if half else 0
        late_eff_a = sum(learning_curve_a[half:]) / max(1, len(learning_curve_a) - half) if len(learning_curve_a) > half else 0
        early_eff_b = sum(learning_curve_b[:half]) / half if half else 0
        late_eff_b = sum(learning_curve_b[half:]) / max(1, len(learning_curve_b) - half) if len(learning_curve_b) > half else 0

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
                    "gen_cost_a": getattr(r, 'gen_cost_a', 0),
                    "gen_cost_b": getattr(r, 'gen_cost_b', 0),
                    "bets": len(getattr(r, 'all_bets', getattr(r, 'bets_placed', []))),
                    "bet_status_counts": _round_bet_status_counts(r),
                    "bets_pending": _round_bet_status_counts(r).get("pending", 0),
                }
                for r in self._results
            ],
            "learning_curve": {
                "a_efficiency_per_round": [round(x, 6) for x in learning_curve_a],
                "b_efficiency_per_round": [round(x, 6) for x in learning_curve_b],
                "a_early_avg": round(early_eff_a, 6),
                "a_late_avg": round(late_eff_a, 6),
                "a_improvement": round(late_eff_a - early_eff_a, 6),
                "b_early_avg": round(early_eff_b, 6),
                "b_late_avg": round(late_eff_b, 6),
                "b_improvement": round(late_eff_b - early_eff_b, 6),
            },
            "final_balances": self.ledger.summary()["balances"],
            "eliminated": self._eliminated,
            "early_stop_reason": self._early_stop_reason,
            "winner": (self.debater_b.name if self._eliminated == self.debater_a.name else self.debater_a.name) if self._eliminated else (self.debater_a.name if self.ledger.balance(self.debater_a.name) > self.ledger.balance(self.debater_b.name) else self.debater_b.name),
        }

        # Save playbooks for veteran experiments
        import os
        playbook_dir = os.path.join(os.path.dirname(path), "playbooks")
        os.makedirs(playbook_dir, exist_ok=True)
        if hasattr(self.debater_a, 'memory') and self.debater_a.memory.entries:
            pb_path = os.path.join(playbook_dir, f"{self.debater_a.name}_playbook.json")
            self.debater_a.memory.save(pb_path)
            summary["playbook_a"] = pb_path
        if hasattr(self.debater_b, 'memory') and self.debater_b.memory.entries:
            pb_path = os.path.join(playbook_dir, f"{self.debater_b.name}_playbook.json")
            self.debater_b.memory.save(pb_path)
            summary["playbook_b"] = pb_path
        with open(path, "w") as f:
            json.dump(summary, f, indent=2)
