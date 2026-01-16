"""
Round: Single debate round logic with proper re-evaluation after counter-arguments.
"""
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from ..models import Debater, Judge, Argument, Judgment, BetType, BetDecision
from ..economy import TokenLedger, BettingManager, TokenDistributor

if TYPE_CHECKING:
    from ..logs import RoundTranscript


@dataclass
class RoundResult:
    round_id: int
    topic: str
    argument_a: Argument
    argument_b: Argument
    initial_judgment: Judgment
    final_judgment: Optional[Judgment]  # After counter-arguments
    tokens_awarded_a: float
    tokens_awarded_b: float
    counter_arguments: list[Argument] = field(default_factory=list)
    bets_placed: list = field(default_factory=list)
    
    @property
    def judgment(self) -> Judgment:
        """For backwards compatibility."""
        return self.final_judgment or self.initial_judgment


class DebateRound:
    """
    Orchestrates a single debate round.
    
    Flow:
    1. Both debaters generate initial arguments
    2. Judge evaluates → initial confidence scores
    3. Tokens distributed based on initial judgment
    4. Debaters decide whether to bet on counter-arguments
    5. Counter-arguments generated (if betting)
    6. Judge RE-EVALUATES with counter-arguments included
    7. Bets resolved: win if your confidence improved
    """
    
    def __init__(
        self,
        debater_a: Debater,
        debater_b: Debater,
        judge: Judge,
        ledger: TokenLedger,
        betting: BettingManager,
        distributor: TokenDistributor,
    ):
        self.debater_a = debater_a
        self.debater_b = debater_b
        self.judge = judge
        self.ledger = ledger
        self.betting = betting
        self.distributor = distributor
    
    def run(
        self,
        topic: str,
        round_id: int,
        transcript: Optional["RoundTranscript"] = None,
        token_cost_ratio: int = 20,  # 20 LLM tokens = 1 economic token
    ) -> RoundResult:
        """Execute a complete debate round."""
        
        # Phase 1: Initial arguments (with token awareness)
        balance_a = self.ledger.balance(self.debater_a.name)
        balance_b = self.ledger.balance(self.debater_b.name)
        arg_a = self.debater_a.generate_argument(topic, round_id, current_balance=balance_a)
        arg_b = self.debater_b.generate_argument(topic, round_id, current_balance=balance_b)
        
        # Deduct token costs (20:1 ratio)
        cost_a = arg_a.llm_tokens_used // token_cost_ratio
        cost_b = arg_b.llm_tokens_used // token_cost_ratio
        if cost_a > 0:
            self.ledger.deduct(self.debater_a.name, cost_a, "generation_cost", round_id)
        if cost_b > 0:
            self.ledger.deduct(self.debater_b.name, cost_b, "generation_cost", round_id)
        
        if transcript:
            transcript.add_argument(self.debater_a.name, arg_a.content)
            transcript.add_argument(self.debater_b.name, arg_b.content)
        
        # Phase 2: Initial judgment
        self.judge.reset()  # Amnesia
        initial_judgment = self.judge.evaluate(
            topic, arg_a.content, arg_b.content, round_id
        )
        
        if transcript:
            transcript.add_judgment(
                self.judge.name + " (initial)",
                initial_judgment.reasoning,
                initial_judgment.confidence_a,
                initial_judgment.confidence_b,
            )
        
        # Phase 3: Initial token distribution
        dist = self.distributor.distribute_linear(
            self.debater_a.name,
            self.debater_b.name,
            initial_judgment.confidence_a,
            initial_judgment.confidence_b,
            round_id,
            self.ledger,
        )
        
        if transcript:
            transcript.tokens_awarded_a = dist.tokens_a
            transcript.tokens_awarded_b = dist.tokens_b
        
        # Phase 4: Betting and counter-arguments
        bets = []
        counter_args = []
        counter_a = None
        counter_b = None
        
        # Debater A decides to bet? (sees scores but not reasoning)
        decision_a = self.debater_a.decide_bet(
            self.ledger.balance(self.debater_a.name),
            arg_b.content,
            arg_a.content,
            confidence_self=initial_judgment.confidence_a,
            confidence_opponent=initial_judgment.confidence_b,
        )
        
        # Log deliberation
        if transcript:
            transcript.add_deliberation(
                self.debater_a.name,
                decision_a.bet_type.value,
                decision_a.amount,
                decision_a.reasoning,
            )
        
        bet_a = None
        research_a = None
        if decision_a.bet_type != BetType.PASS:
            bet_a = self.betting.place_bet(
                self.debater_a.name, decision_a.amount, round_id, self.ledger
            )
            if bet_a:
                bets.append(bet_a)
                current_bal_a = self.ledger.balance(self.debater_a.name)
                
                if decision_a.bet_type == BetType.REFUTATION:
                    # Counter opponent's argument
                    counter_a = self.debater_a.generate_argument(
                        topic, round_id, opponent_argument=arg_b.content, current_balance=current_bal_a
                    )
                    counter_cost_a = counter_a.llm_tokens_used // token_cost_ratio
                    if counter_cost_a > 0:
                        self.ledger.deduct(self.debater_a.name, counter_cost_a, "counter_generation_cost", round_id)
                    counter_a.tokens_bet = decision_a.amount
                    counter_args.append(counter_a)
                    if transcript:
                        transcript.add_argument(
                            self.debater_a.name, counter_a.content,
                            is_counter=True, tokens_bet=decision_a.amount
                        )
                else:
                    # Research: strengthen own argument
                    research_a = self.debater_a.generate_research(
                        topic, round_id, arg_a.content, current_balance=current_bal_a
                    )
                    research_cost_a = research_a.llm_tokens_used // token_cost_ratio
                    if research_cost_a > 0:
                        self.ledger.deduct(self.debater_a.name, research_cost_a, "research_generation_cost", round_id)
                    research_a.tokens_bet = decision_a.amount
                    counter_args.append(research_a)
                    if transcript:
                        transcript.add_argument(
                            self.debater_a.name, research_a.content,
                            is_counter=False, tokens_bet=decision_a.amount
                        )
        
        # Debater B decides to bet? (sees scores but not reasoning)
        decision_b = self.debater_b.decide_bet(
            self.ledger.balance(self.debater_b.name),
            arg_a.content,
            arg_b.content,
            confidence_self=initial_judgment.confidence_b,
            confidence_opponent=initial_judgment.confidence_a,
        )
        
        # Log deliberation
        if transcript:
            transcript.add_deliberation(
                self.debater_b.name,
                decision_b.bet_type.value,
                decision_b.amount,
                decision_b.reasoning,
            )
        
        bet_b = None
        research_b = None
        if decision_b.bet_type != BetType.PASS:
            bet_b = self.betting.place_bet(
                self.debater_b.name, decision_b.amount, round_id, self.ledger
            )
            if bet_b:
                bets.append(bet_b)
                current_bal_b = self.ledger.balance(self.debater_b.name)
                
                if decision_b.bet_type == BetType.REFUTATION:
                    # Counter opponent's argument
                    counter_b = self.debater_b.generate_argument(
                        topic, round_id, opponent_argument=arg_a.content, current_balance=current_bal_b
                    )
                    counter_cost_b = counter_b.llm_tokens_used // token_cost_ratio
                    if counter_cost_b > 0:
                        self.ledger.deduct(self.debater_b.name, counter_cost_b, "counter_generation_cost", round_id)
                    counter_b.tokens_bet = decision_b.amount
                    counter_args.append(counter_b)
                    if transcript:
                        transcript.add_argument(
                            self.debater_b.name, counter_b.content,
                            is_counter=True, tokens_bet=decision_b.amount
                        )
                else:
                    # Research: strengthen own argument
                    research_b = self.debater_b.generate_research(
                        topic, round_id, arg_b.content, current_balance=current_bal_b
                    )
                    research_cost_b = research_b.llm_tokens_used // token_cost_ratio
                    if research_cost_b > 0:
                        self.ledger.deduct(self.debater_b.name, research_cost_b, "research_generation_cost", round_id)
                    research_b.tokens_bet = decision_b.amount
                    counter_args.append(research_b)
                    if transcript:
                        transcript.add_argument(
                            self.debater_b.name, research_b.content,
                            is_counter=False, tokens_bet=decision_b.amount
                        )
        
        # Phase 5: Re-evaluation if any bets were placed
        final_judgment = None
        if bets:
            # Build combined arguments for re-evaluation
            combined_a = arg_a.content
            combined_b = arg_b.content
            
            # Add counter-arguments or research
            if counter_a:
                combined_a += f"\n\n[COUNTER-ARGUMENT]\n{counter_a.content}"
            if research_a:
                combined_a += f"\n\n[ADDITIONAL RESEARCH]\n{research_a.content}"
            if counter_b:
                combined_b += f"\n\n[COUNTER-ARGUMENT]\n{counter_b.content}"
            if research_b:
                combined_b += f"\n\n[ADDITIONAL RESEARCH]\n{research_b.content}"
            
            # Judge re-evaluates with fresh eyes (amnesia)
            self.judge.reset()
            final_judgment = self.judge.evaluate(
                topic, combined_a, combined_b, round_id
            )
            
            if transcript:
                transcript.add_judgment(
                    self.judge.name + " (final)",
                    final_judgment.reasoning,
                    final_judgment.confidence_a,
                    final_judgment.confidence_b,
                )
            
            # Phase 6: Resolve bets based on confidence change
            if bet_a:
                # A wins if their confidence improved
                improved = final_judgment.confidence_a > initial_judgment.confidence_a
                self.betting.resolve_bet(bet_a, improved, multiplier=1.8, ledger=self.ledger)
                if transcript:
                    transcript.add_bet_resolution(self.debater_a.name, improved, bet_a.payout)
            
            if bet_b:
                # B wins if their confidence improved
                improved = final_judgment.confidence_b > initial_judgment.confidence_b
                self.betting.resolve_bet(bet_b, improved, multiplier=1.8, ledger=self.ledger)
                if transcript:
                    transcript.add_bet_resolution(self.debater_b.name, improved, bet_b.payout)
        
        return RoundResult(
            round_id=round_id,
            topic=topic,
            argument_a=arg_a,
            argument_b=arg_b,
            initial_judgment=initial_judgment,
            final_judgment=final_judgment,
            tokens_awarded_a=dist.tokens_a,
            tokens_awarded_b=dist.tokens_b,
            counter_arguments=counter_args,
            bets_placed=bets,
        )
