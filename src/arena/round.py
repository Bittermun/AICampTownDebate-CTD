"""
Round: Single debate round logic with proper re-evaluation after counter-arguments.
Refactored into discrete phases with explicit state management.
"""
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING, List
from ..models import Debater, BaseJudge, Argument, Judgment, BetType, BetDecision
from ..economy import TokenLedger, BettingManager, TokenDistributor, Bet

if TYPE_CHECKING:
    from ..logs import RoundTranscript


@dataclass
class RoundContext:
    """Explicit state container for round execution.
    
    All phase functions read from and write to this context,
    making state flow explicit and testable.
    """
    round_id: int
    topic: str
    token_cost_ratio: int = 20
    
    # Phase 1: Arguments
    arg_a: Optional[Argument] = None
    arg_b: Optional[Argument] = None
    
    # Phase 2: Initial Judgment
    initial_judgment: Optional[Judgment] = None
    
    # Phase 3: Betting
    decision_a: Optional[BetDecision] = None
    decision_b: Optional[BetDecision] = None
    bet_a: Optional[Bet] = None
    bet_b: Optional[Bet] = None
    counter_a: Optional[Argument] = None
    counter_b: Optional[Argument] = None
    research_a: Optional[Argument] = None
    research_b: Optional[Argument] = None
    round_pot_extra: float = 0.0
    counter_args: List[Argument] = field(default_factory=list)
    bets: List[Bet] = field(default_factory=list)
    
    # Phase 4: Final Judgment
    final_judgment: Optional[Judgment] = None
    
    # Phase 5: Distribution
    tokens_awarded_a: float = 0.0
    tokens_awarded_b: float = 0.0


@dataclass
class RoundResult:
    round_id: int
    topic: str
    argument_a: Argument
    argument_b: Argument
    initial_judgment: Judgment
    final_judgment: Optional[Judgment]
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
    3. Debaters decide whether to bet on counter-arguments
    4. Counter-arguments generated (if betting)
    5. Judge RE-EVALUATES with counter-arguments included
    6. Tokens distributed via pot split
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
        token_cost_ratio: int = 20,
    ) -> RoundResult:
        """Execute a complete debate round via phase pipeline."""
        ctx = RoundContext(round_id=round_id, topic=topic, token_cost_ratio=token_cost_ratio)
        
        ctx = self._phase_generate_arguments(ctx, transcript)
        ctx = self._phase_initial_judgment(ctx, transcript)
        ctx = self._phase_betting(ctx, transcript)
        ctx = self._phase_final_judgment(ctx, transcript)
        ctx = self._phase_distribute_tokens(ctx, transcript)
        
        return self._build_result(ctx)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1: Generate Arguments
    # ─────────────────────────────────────────────────────────────────────────
    
    def _phase_generate_arguments(
        self, ctx: RoundContext, transcript: Optional["RoundTranscript"]
    ) -> RoundContext:
        """Both debaters generate initial arguments with token awareness."""
        balance_a = self.ledger.balance(self.debater_a.name)
        balance_b = self.ledger.balance(self.debater_b.name)
        
        ctx.arg_a = self.debater_a.generate_argument(ctx.topic, ctx.round_id, current_balance=balance_a)
        ctx.arg_b = self.debater_b.generate_argument(ctx.topic, ctx.round_id, current_balance=balance_b)
        
        # Deduct token costs (20:1 ratio)
        cost_a = ctx.arg_a.llm_tokens_used // ctx.token_cost_ratio
        cost_b = ctx.arg_b.llm_tokens_used // ctx.token_cost_ratio
        
        if cost_a > 0:
            self.ledger.deduct(self.debater_a.name, cost_a, "generation_cost", ctx.round_id)
        if cost_b > 0:
            self.ledger.deduct(self.debater_b.name, cost_b, "generation_cost", ctx.round_id)
        
        if transcript:
            transcript.add_argument(self.debater_a.name, ctx.arg_a.content)
            transcript.add_argument(self.debater_b.name, ctx.arg_b.content)
        
        # Postcondition: arguments must exist
        assert ctx.arg_a is not None, "Phase 1 failed: arg_a not generated"
        assert ctx.arg_b is not None, "Phase 1 failed: arg_b not generated"
        return ctx
    
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 2: Initial Judgment
    # ─────────────────────────────────────────────────────────────────────────
    
    def _phase_initial_judgment(
        self, ctx: RoundContext, transcript: Optional["RoundTranscript"]
    ) -> RoundContext:
        """Judge evaluates initial arguments."""
        self.judge.reset()  # Amnesia
        ctx.initial_judgment = self.judge.evaluate(
            ctx.topic, ctx.arg_a.content, ctx.arg_b.content, ctx.round_id
        )
        
        if transcript:
            transcript.add_judgment(
                self.judge.name + " (initial)",
                ctx.initial_judgment.reasoning,
                ctx.initial_judgment.confidence_a,
                ctx.initial_judgment.confidence_b,
                sub_judgments=ctx.initial_judgment.sub_judgments
            )
        
        # Postcondition: judgment must exist with valid confidences
        assert ctx.initial_judgment is not None, "Phase 2 failed: no judgment"
        assert 0 <= ctx.initial_judgment.confidence_a <= 1, "Invalid confidence_a"
        assert 0 <= ctx.initial_judgment.confidence_b <= 1, "Invalid confidence_b"
        return ctx
    
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 3: Betting (REFUTE / RESEARCH / PASS)
    # ─────────────────────────────────────────────────────────────────────────
    
    def _phase_betting(
        self, ctx: RoundContext, transcript: Optional["RoundTranscript"]
    ) -> RoundContext:
        """Collect betting decisions and generate counter-arguments/research."""
        # Debater A decides
        ctx = self._process_debater_bet(
            ctx, transcript,
            debater=self.debater_a,
            own_arg=ctx.arg_a,
            opponent_arg=ctx.arg_b,
            conf_self=ctx.initial_judgment.confidence_a,
            conf_opponent=ctx.initial_judgment.confidence_b,
            is_debater_a=True,
        )
        
        # Debater B decides
        ctx = self._process_debater_bet(
            ctx, transcript,
            debater=self.debater_b,
            own_arg=ctx.arg_b,
            opponent_arg=ctx.arg_a,
            conf_self=ctx.initial_judgment.confidence_b,
            conf_opponent=ctx.initial_judgment.confidence_a,
            is_debater_a=False,
        )
        
        return ctx
    
    def _process_debater_bet(
        self,
        ctx: RoundContext,
        transcript: Optional["RoundTranscript"],
        debater: Debater,
        own_arg: Argument,
        opponent_arg: Argument,
        conf_self: float,
        conf_opponent: float,
        is_debater_a: bool,
    ) -> RoundContext:
        """Process a single debater's betting decision."""
        decision = debater.decide_bet(
            self.ledger.balance(debater.name),
            opponent_arg.content,
            own_arg.content,
            confidence_self=conf_self,
            confidence_opponent=conf_opponent,
        )
        
        if transcript:
            transcript.add_deliberation(
                debater.name,
                decision.bet_type.value,
                decision.amount,
                decision.reasoning,
            )
        
        # Store decision
        if is_debater_a:
            ctx.decision_a = decision
        else:
            ctx.decision_b = decision
        
        if decision.bet_type == BetType.PASS:
            return ctx
        
        # Place bet
        bet = self.betting.place_bet(debater.name, decision.amount, ctx.round_id, self.ledger)
        if not bet:
            return ctx
        
        ctx.bets.append(bet)
        ctx.round_pot_extra += bet.amount
        
        if is_debater_a:
            ctx.bet_a = bet
        else:
            ctx.bet_b = bet
        
        current_bal = self.ledger.balance(debater.name)
        
        # Generate counter or research
        if decision.bet_type == BetType.REFUTATION:
            counter = debater.generate_argument(
                ctx.topic, ctx.round_id,
                opponent_argument=opponent_arg.content,
                current_balance=current_bal,
                confidence_self=conf_self,
                confidence_opponent=conf_opponent,
            )
            counter_cost = counter.llm_tokens_used // ctx.token_cost_ratio
            if counter_cost > 0:
                self.ledger.deduct(debater.name, counter_cost, "counter_generation_cost", ctx.round_id)
            counter.tokens_bet = decision.amount
            ctx.counter_args.append(counter)
            
            if is_debater_a:
                ctx.counter_a = counter
            else:
                ctx.counter_b = counter
            
            if transcript:
                transcript.add_argument(debater.name, counter.content, is_counter=True, tokens_bet=decision.amount)
        else:
            # RESEARCH
            research = debater.generate_research(
                ctx.topic, ctx.round_id,
                own_arg.content,
                current_balance=current_bal,
                confidence_self=conf_self,
                confidence_opponent=conf_opponent,
            )
            research_cost = research.llm_tokens_used // ctx.token_cost_ratio
            if research_cost > 0:
                self.ledger.deduct(debater.name, research_cost, "research_generation_cost", ctx.round_id)
            research.tokens_bet = decision.amount
            ctx.counter_args.append(research)
            
            if is_debater_a:
                ctx.research_a = research
            else:
                ctx.research_b = research
            
            if transcript:
                transcript.add_argument(debater.name, research.content, is_counter=False, tokens_bet=decision.amount)
        
        return ctx
    
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 4: Final Judgment
    # ─────────────────────────────────────────────────────────────────────────
    
    def _phase_final_judgment(
        self, ctx: RoundContext, transcript: Optional["RoundTranscript"]
    ) -> RoundContext:
        """Judge re-evaluates with combined arguments."""
        # Build combined arguments
        combined_a = ctx.arg_a.content
        combined_b = ctx.arg_b.content
        
        if ctx.counter_a:
            combined_a += f"\n\n[COUNTER-ARGUMENT]\n{ctx.counter_a.content}"
        if ctx.research_a:
            combined_a += f"\n\n[RESEARCH]\n{ctx.research_a.content}"
        if ctx.counter_b:
            combined_b += f"\n\n[COUNTER-ARGUMENT]\n{ctx.counter_b.content}"
        if ctx.research_b:
            combined_b += f"\n\n[RESEARCH]\n{ctx.research_b.content}"
        
        self.judge.reset()
        ctx.final_judgment = self.judge.evaluate(ctx.topic, combined_a, combined_b, ctx.round_id)
        
        if transcript:
            transcript.add_judgment(
                self.judge.name + " (final)",
                ctx.final_judgment.reasoning,
                ctx.final_judgment.confidence_a,
                ctx.final_judgment.confidence_b,
                sub_judgments=ctx.final_judgment.sub_judgments
            )
        
        # Postcondition: final judgment must exist
        assert ctx.final_judgment is not None, "Phase 4 failed: no final judgment"
        return ctx
    
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 5: Distribute Tokens
    # ─────────────────────────────────────────────────────────────────────────
    
    def _phase_distribute_tokens(
        self, ctx: RoundContext, transcript: Optional["RoundTranscript"]
    ) -> RoundContext:
        """Pot split and bet resolution."""
        dist = self.distributor.distribute_pot(
            self.debater_a.name,
            self.debater_b.name,
            ctx.final_judgment.confidence_a,
            ctx.final_judgment.confidence_b,
            ctx.round_id,
            self.ledger,
            extra_pot_tokens=ctx.round_pot_extra
        )
        
        ctx.tokens_awarded_a = dist.tokens_a
        ctx.tokens_awarded_b = dist.tokens_b
        
        if transcript:
            transcript.tokens_awarded_a = dist.tokens_a
            transcript.tokens_awarded_b = dist.tokens_b
            
            # Record bet outcomes
            if ctx.bet_a:
                won = ctx.final_judgment.confidence_a > ctx.initial_judgment.confidence_a
                transcript.add_bet_resolution(self.debater_a.name, won, dist.tokens_a, fee_paid=ctx.bet_a.fee_paid)
            if ctx.bet_b:
                won = ctx.final_judgment.confidence_b > ctx.initial_judgment.confidence_b
                transcript.add_bet_resolution(self.debater_b.name, won, dist.tokens_b, fee_paid=ctx.bet_b.fee_paid)
        
        return ctx
    
    # ─────────────────────────────────────────────────────────────────────────
    # Build Result
    # ─────────────────────────────────────────────────────────────────────────
    
    def _build_result(self, ctx: RoundContext) -> RoundResult:
        """Convert RoundContext to RoundResult."""
        return RoundResult(
            round_id=ctx.round_id,
            topic=ctx.topic,
            argument_a=ctx.arg_a,
            argument_b=ctx.arg_b,
            initial_judgment=ctx.initial_judgment,
            final_judgment=ctx.final_judgment,
            tokens_awarded_a=ctx.tokens_awarded_a,
            tokens_awarded_b=ctx.tokens_awarded_b,
            counter_arguments=ctx.counter_args,
            bets_placed=ctx.bets,
        )
