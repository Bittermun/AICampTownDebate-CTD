"""
Round: Single debate round logic with proper re-evaluation after counter-arguments.
"""
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from ..models import Debater, BaseJudge, Argument, Judgment, BetType, BetDecision
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
        judge: BaseJudge,
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
        
        # Phase 3: Initial judgment (No award yet, just recording)
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
                sub_judgments=initial_judgment.sub_judgments
            )
        
        # Phase 4: Betting and counter-arguments
        bets = []
        counter_args = []
        counter_a = None
        counter_b = None
        round_pot_extra = 0.0
        
        # Debater A decides to bet?
        decision_a = self.debater_a.decide_bet(
            self.ledger.balance(self.debater_a.name),
            arg_b.content,
            arg_a.content,
            confidence_self=initial_judgment.confidence_a,
            confidence_opponent=initial_judgment.confidence_b,
        )
        
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
                round_pot_extra += bet_a.amount
                current_bal_a = self.ledger.balance(self.debater_a.name)
                
                if decision_a.bet_type == BetType.REFUTATION:
                    counter_a = self.debater_a.generate_argument(
                        topic, round_id, 
                        opponent_argument=arg_b.content, 
                        current_balance=current_bal_a,
                        confidence_self=initial_judgment.confidence_a,
                        confidence_opponent=initial_judgment.confidence_b,
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
                    research_a = self.debater_a.generate_research(
                        topic, round_id, 
                        arg_a.content, 
                        current_balance=current_bal_a,
                        confidence_self=initial_judgment.confidence_a,
                        confidence_opponent=initial_judgment.confidence_b,
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
        
        # Debater B decides to bet?
        decision_b = self.debater_b.decide_bet(
            self.ledger.balance(self.debater_b.name),
            arg_a.content,
            arg_b.content,
            confidence_self=initial_judgment.confidence_b,
            confidence_opponent=initial_judgment.confidence_a,
        )
        
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
                round_pot_extra += bet_b.amount
                current_bal_b = self.ledger.balance(self.debater_b.name)
                
                if decision_b.bet_type == BetType.REFUTATION:
                    counter_b = self.debater_b.generate_argument(
                        topic, round_id, 
                        opponent_argument=arg_a.content, 
                        current_balance=current_bal_b,
                        confidence_self=initial_judgment.confidence_b,
                        confidence_opponent=initial_judgment.confidence_a,
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
                    research_b = self.debater_b.generate_research(
                        topic, round_id, 
                        arg_b.content, 
                        current_balance=current_bal_b,
                        confidence_self=initial_judgment.confidence_b,
                        confidence_opponent=initial_judgment.confidence_a,
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
        
        # Phase 5: Re-evaluation
        final_judgment = None
        
        # Build combined arguments
        combined_a = arg_a.content
        combined_b = arg_b.content
        if counter_a: combined_a += f"\n\n[COUNTER-ARGUMENT]\n{counter_a.content}"
        if research_a: combined_a += f"\n\n[RESEARCH]\n{research_a.content}"
        if counter_b: combined_b += f"\n\n[COUNTER-ARGUMENT]\n{counter_b.content}"
        if research_b: combined_b += f"\n\n[RESEARCH]\n{research_b.content}"
        
        # Judge re-evaluates
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
                sub_judgments=final_judgment.sub_judgments
            )
        
        # Phase 6: Resolved Pool Split
        dist = self.distributor.distribute_pot(
            self.debater_a.name,
            self.debater_b.name,
            final_judgment.confidence_a,
            final_judgment.confidence_b,
            round_id,
            self.ledger,
            extra_pot_tokens=round_pot_extra
        )
        
        if transcript:
            transcript.tokens_awarded_a = dist.tokens_a
            transcript.tokens_awarded_b = dist.tokens_b
            
            # Record virtual bet outcomes for transcript
            if bet_a:
                won = final_judgment.confidence_a > initial_judgment.confidence_a
                transcript.add_bet_resolution(self.debater_a.name, won, dist.tokens_a)
            if bet_b:
                won = final_judgment.confidence_b > initial_judgment.confidence_b
                transcript.add_bet_resolution(self.debater_b.name, won, dist.tokens_b)
        
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
