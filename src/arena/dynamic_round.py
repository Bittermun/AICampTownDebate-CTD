"""
DynamicDebateRound: Debate round that continues until both debaters PASS.

Unlike the fixed DebateRound, this class runs an iterative loop where:
1. Initial arguments + judgment happen once
2. Betting iterations continue until mutual PASS or safety limit
3. Pot is locked until endgame (final distribution)
"""
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING, List
from ..models import Debater, BaseJudge, Argument, Judgment, BetType, BetDecision
from ..economy import TokenLedger, BettingManager, TokenDistributor, Bet
from ..logs import Turn  # For transcript entries
from ..tools import get_research_tool

if TYPE_CHECKING:
    from ..logs import RoundTranscript

@dataclass
class DynamicRoundContext:
    """State container for dynamic round execution."""
    round_id: int
    topic: str
    debater_a_id: str = ""
    debater_b_id: str = ""
    token_cost_ratio: int = 20
    max_iterations: int = 10
    ledger: Optional[TokenLedger] = None
    
    # Current iteration
    iteration: int = 0
    
    # Initial arguments (generated once)
    arg_a: Optional[Argument] = None
    arg_b: Optional[Argument] = None
    
    # Combined arguments (built up over iterations)
    combined_a: str = ""
    combined_b: str = ""
    
    # Judgments
    initial_judgment: Optional[Judgment] = None
    current_judgment: Optional[Judgment] = None  # Updated each iteration
    
    # Iteration state
    decision_a: Optional[BetDecision] = None
    decision_b: Optional[BetDecision] = None
    
    # Accumulated pot (locked until endgame)
    locked_pot: float = 0.0
    all_bets: List[Bet] = field(default_factory=list)
    all_counters: List[Argument] = field(default_factory=list)
    
    # Metrics tracking (for observers)
    initial_balance_a: float = 0.0  # Starting balance
    initial_balance_b: float = 0.0
    final_balance_a: float = 0.0
    final_balance_b: float = 0.0
    gen_cost_a: float = 0.0  # Cumulative generation cost
    gen_cost_b: float = 0.0
    total_bet_amount_a: float = 0.0  # Total tokens bet (before fees)
    total_bet_amount_b: float = 0.0
    bet_count_a: int = 0
    bet_count_b: int = 0
    pass_count_a: int = 0
    pass_count_b: int = 0
    validation_fallback_a: int = 0  # Count of PASS due to JSON parse failures
    validation_fallback_b: int = 0
    confidence_trajectory: List[tuple] = field(default_factory=list)  # [(iter, conf_a, conf_b)]
    
    # Self-summarization memory (compressed position for each debater)
    summary_a: str = ""  # Debater A's compressed position summary
    summary_b: str = ""  # Debater B's compressed position summary
    
    # Termination tracking
    iterations_completed: int = 0
    termination_reason: str = ""  # "mutual_pass", "max_iterations", "bankruptcy"
    
    # Final distribution
    tokens_awarded_a: float = 0.0
    tokens_awarded_b: float = 0.0
    round_supply_start: float = 0.0
    round_supply_end: float = 0.0
    round_minted: float = 0.0
    round_burned: float = 0.0
    round_net_supply_change: float = 0.0
    accounting_ok: bool = True
    accounting_notes: List[str] = field(default_factory=list)


@dataclass
class DynamicRoundResult:
    """Result of a dynamic debate round."""
    round_id: int
    topic: str
    argument_a: Argument
    argument_b: Argument
    initial_judgment: Judgment
    final_judgment: Judgment
    tokens_awarded_a: float
    tokens_awarded_b: float
    iterations_completed: int
    termination_reason: str
    all_bets: List[Bet] = field(default_factory=list)
    all_counters: List[Argument] = field(default_factory=list)
    observation_reports: List = field(default_factory=list)  # ObservationReport list
    
    @property
    def judgment(self) -> Judgment:
        """For backwards compatibility."""
        return self.final_judgment


class DynamicDebateRound:
    """
    Orchestrates a debate round with AI-driven duration.
    
    Flow:
    1. Both debaters generate initial arguments
    2. Judge evaluates → initial confidence scores
    3. LOOP until termination:
       a. Debaters decide: BET (continue) or PASS (wait)
       b. If both PASS → exit loop
       c. Generate counter/research for active bettors
       d. Judge re-evaluates
       e. Check bankruptcy / max iterations
    4. Final distribution via pot split
    """
    
    def __init__(
        self,
        debater_a: Debater,
        debater_b: Debater,
        judge: BaseJudge,
        ledger: TokenLedger,
        betting: BettingManager,
        distributor: TokenDistributor,
        max_iterations: int = 10,
        observers: Optional[List] = None,  # List of Observer protocol objects
        split_pot_enabled: bool = False,   # Pay initial bounty after first judgment
        initial_pot_amount: float = 40.0,  # Amount to distribute as initial bounty
    ):
        self.debater_a = debater_a
        self.debater_b = debater_b
        self.judge = judge
        self.ledger = ledger
        self.betting = betting
        self.distributor = distributor
        self.max_iterations = max_iterations
        self.observers = observers or []
        self.split_pot_enabled = split_pot_enabled
        self.initial_pot_amount = initial_pot_amount

    
    def run(
        self,
        topic: str,
        round_id: int,
        transcript: Optional["RoundTranscript"] = None,
        token_cost_ratio: int = 20,
    ) -> DynamicRoundResult:
        """Execute a dynamic debate round."""
        ctx = DynamicRoundContext(
            round_id=round_id,
            topic=topic,
            debater_a_id=self.debater_a.name,
            debater_b_id=self.debater_b.name,
            token_cost_ratio=token_cost_ratio,
            max_iterations=self.max_iterations,
            ledger=self.ledger,
        )
        
        # Capture initial balances for metrics
        ctx.initial_balance_a = self.ledger.balance(self.debater_a.name)
        ctx.initial_balance_b = self.ledger.balance(self.debater_b.name)
        ctx.round_supply_start = sum(self.ledger.summary()["balances"].values())
        
        # Phase 1: Generate initial arguments (once)
        ctx = self._phase_generate_arguments(ctx, transcript)
        
        # Phase 2: Initial judgment (once)
        ctx = self._phase_initial_judgment(ctx, transcript)
        
        # Record initial confidence
        ctx.confidence_trajectory.append((
            0, ctx.initial_judgment.confidence_a, ctx.initial_judgment.confidence_b
        ))
        
        # Phase 2b: Initial Bounty Distribution (if split pot enabled)
        if self.split_pot_enabled and self.initial_pot_amount > 0:
            # Calculate split based on initial confidence
            total_conf = ctx.initial_judgment.confidence_a + ctx.initial_judgment.confidence_b
            if total_conf > 0:
                tokens_a = self.initial_pot_amount * (ctx.initial_judgment.confidence_a / total_conf)
                tokens_b = self.initial_pot_amount * (ctx.initial_judgment.confidence_b / total_conf)
            else:
                tokens_a = self.initial_pot_amount / 2
                tokens_b = self.initial_pot_amount / 2
            
            # Award to ledger (credit = award in TokenLedger API)
            self.ledger.award(self.debater_a.name, tokens_a, "initial_bounty", ctx.round_id)
            self.ledger.award(self.debater_b.name, tokens_b, "initial_bounty", ctx.round_id)
            
            # Track in context for observers
            ctx.tokens_awarded_a += tokens_a
            ctx.tokens_awarded_b += tokens_b
            
            if transcript:
                transcript.tokens_awarded_a += tokens_a
                transcript.tokens_awarded_b += tokens_b
                transcript.turns.append(Turn(
                    speaker="System",
                    content=f"**Initial Bounty Distributed**: A={tokens_a:.1f}, B={tokens_b:.1f} (from {self.initial_pot_amount} pot)",
                    turn_type="payout",
                    round_id=ctx.round_id,
                ))

        
        # Phase 3: Iterative betting loop
        ctx = self._betting_loop(ctx, transcript)

        
        # Phase 4: Final distribution
        ctx = self._phase_distribute_tokens(ctx, transcript)

        # Final balances and accounting audit (single source of truth = ledger).
        ctx.final_balance_a = self.ledger.balance(self.debater_a.name)
        ctx.final_balance_b = self.ledger.balance(self.debater_b.name)
        self._audit_round_accounting(ctx)
        
        # Finalize observers AFTER distribution (so they see tokens_awarded)
        observation_reports = []
        for observer in self.observers:
            try:
                report = observer.finalize(ctx)
                observation_reports.append(report)
            except Exception as e:
                print(f"  [Warning] Observer {observer.name} failed: {e}")
        
        return self._build_result(ctx, observation_reports)
    
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 1: Generate Arguments (runs once)
    # ─────────────────────────────────────────────────────────────────────────
    
    def _phase_generate_arguments(
        self, ctx: DynamicRoundContext, transcript: Optional["RoundTranscript"]
    ) -> DynamicRoundContext:
        """Both debaters generate initial arguments."""
        balance_a = self.ledger.balance(self.debater_a.name)
        balance_b = self.ledger.balance(self.debater_b.name)
        
        ctx.arg_a = self.debater_a.generate_argument(ctx.topic, ctx.round_id, current_balance=balance_a)
        ctx.arg_b = self.debater_b.generate_argument(ctx.topic, ctx.round_id, current_balance=balance_b)
        
        # Deduct token costs
        cost_a = ctx.arg_a.llm_tokens_used // ctx.token_cost_ratio
        cost_b = ctx.arg_b.llm_tokens_used // ctx.token_cost_ratio
        
        if cost_a > 0:
            self.ledger.deduct(self.debater_a.name, cost_a, "generation_cost", ctx.round_id)
        if cost_b > 0:
            self.ledger.deduct(self.debater_b.name, cost_b, "generation_cost", ctx.round_id)
        
        # Initialize combined arguments
        ctx.combined_a = ctx.arg_a.content
        ctx.combined_b = ctx.arg_b.content
        
        if transcript:
            transcript.add_argument(self.debater_a.name, ctx.arg_a.content)
            transcript.add_argument(self.debater_b.name, ctx.arg_b.content)
        
        assert ctx.arg_a is not None, "Phase 1 failed: arg_a not generated"
        assert ctx.arg_b is not None, "Phase 1 failed: arg_b not generated"
        return ctx
    
    async def _phase_generate_arguments_async(
        self, ctx: DynamicRoundContext, transcript: Optional["RoundTranscript"]
    ) -> DynamicRoundContext:
        """Both debaters generate initial arguments IN PARALLEL.
        
        Uses asyncio.gather for concurrent generation, reducing wall-clock time.
        """
        import asyncio
        
        balance_a = self.ledger.balance(self.debater_a.name)
        balance_b = self.ledger.balance(self.debater_b.name)
        
        # Parallel generation
        ctx.arg_a, ctx.arg_b = await asyncio.gather(
            self.debater_a.generate_argument_async(ctx.topic, ctx.round_id, current_balance=balance_a),
            self.debater_b.generate_argument_async(ctx.topic, ctx.round_id, current_balance=balance_b),
        )
        
        # Deduct token costs
        cost_a = ctx.arg_a.llm_tokens_used // ctx.token_cost_ratio
        cost_b = ctx.arg_b.llm_tokens_used // ctx.token_cost_ratio
        
        if cost_a > 0:
            self.ledger.deduct(self.debater_a.name, cost_a, "generation_cost", ctx.round_id)
        if cost_b > 0:
            self.ledger.deduct(self.debater_b.name, cost_b, "generation_cost", ctx.round_id)
        
        # Initialize combined arguments
        ctx.combined_a = ctx.arg_a.content
        ctx.combined_b = ctx.arg_b.content
        
        if transcript:
            transcript.add_argument(self.debater_a.name, ctx.arg_a.content)
            transcript.add_argument(self.debater_b.name, ctx.arg_b.content)
        
        assert ctx.arg_a is not None, "Phase 1 failed: arg_a not generated"
        assert ctx.arg_b is not None, "Phase 1 failed: arg_b not generated"
        return ctx
    
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 2: Initial Judgment (runs once)
    # ─────────────────────────────────────────────────────────────────────────
    
    def _phase_initial_judgment(
        self, ctx: DynamicRoundContext, transcript: Optional["RoundTranscript"]
    ) -> DynamicRoundContext:
        """Judge evaluates initial arguments."""
        self.judge.reset()
        ctx.initial_judgment = self.judge.evaluate(
            ctx.topic, ctx.arg_a.content, ctx.arg_b.content, ctx.round_id
        )
        ctx.current_judgment = ctx.initial_judgment
        
        if transcript:
            transcript.add_judgment(
                self.judge.name + " (initial)",
                ctx.initial_judgment.reasoning,
                ctx.initial_judgment.confidence_a,
                ctx.initial_judgment.confidence_b,
                sub_judgments=ctx.initial_judgment.sub_judgments
            )
        
        assert ctx.initial_judgment is not None, "Phase 2 failed: no judgment"
        return ctx
    
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 3: Betting Loop (iterates until termination)
    # ─────────────────────────────────────────────────────────────────────────
    
    def _betting_loop(
        self, ctx: DynamicRoundContext, transcript: Optional["RoundTranscript"]
    ) -> DynamicRoundContext:
        """Iterative betting loop until termination condition."""
        
        prev_balance_a = self.ledger.balance(self.debater_a.name)
        prev_balance_b = self.ledger.balance(self.debater_b.name)
        
        while ctx.iteration < ctx.max_iterations:
            ctx.iteration += 1
            
            # Get current balances
            balance_a = self.ledger.balance(self.debater_a.name)
            balance_b = self.ledger.balance(self.debater_b.name)
            
            balance_change_a = balance_a - prev_balance_a
            balance_change_b = balance_b - prev_balance_b
            
            # Check bankruptcy
            if balance_a <= -self.ledger.max_debt:
                ctx.termination_reason = "bankruptcy_a"
                break
            if balance_b <= -self.ledger.max_debt:
                ctx.termination_reason = "bankruptcy_b"
                break
            
            # Debaters decide
            current_fee_rate = min(0.05 * ctx.iteration, 0.50)
            ctx.decision_a = self.debater_a.decide_bet(
                balance_a,
                ctx.combined_b,
                ctx.combined_a,
                confidence_self=ctx.current_judgment.confidence_a,
                confidence_opponent=ctx.current_judgment.confidence_b,
                balance_change=balance_change_a,
                current_fee_rate=current_fee_rate,
            )
            
            ctx.decision_b = self.debater_b.decide_bet(
                balance_b,
                ctx.combined_a,
                ctx.combined_b,
                confidence_self=ctx.current_judgment.confidence_b,
                confidence_opponent=ctx.current_judgment.confidence_a,
                balance_change=balance_change_b,
                current_fee_rate=current_fee_rate,
            )
            
            # Deduct deliberation costs (thinking is not free!)
            delib_cost_a = ctx.decision_a.llm_tokens_used // ctx.token_cost_ratio
            delib_cost_b = ctx.decision_b.llm_tokens_used // ctx.token_cost_ratio
            
            if delib_cost_a > 0:
                self.ledger.deduct(self.debater_a.name, delib_cost_a, "deliberation_cost", ctx.round_id)
                ctx.gen_cost_a += delib_cost_a
            if delib_cost_b > 0:
                self.ledger.deduct(self.debater_b.name, delib_cost_b, "deliberation_cost", ctx.round_id)
                ctx.gen_cost_b += delib_cost_b
            
            # Track validation fallbacks (JSON parse failures that forced PASS)
            if "[VALIDATION_FAILED]" in ctx.decision_a.reasoning:
                ctx.validation_fallback_a += 1
            if "[VALIDATION_FAILED]" in ctx.decision_b.reasoning:
                ctx.validation_fallback_b += 1
            
            # Log deliberations with inference-time thinking to transcript
            # Update balances after deliberation costs
            balance_a = self.ledger.balance(self.debater_a.name)
            balance_b = self.ledger.balance(self.debater_b.name)

            
            if transcript:
                transcript.add_deliberation(
                    self.debater_a.name,
                    ctx.decision_a.bet_type.value,
                    ctx.decision_a.amount,
                    f"[Iter {ctx.iteration}] {ctx.decision_a.reasoning}",
                    include_context=True,
                    balance=balance_a,
                    confidence_self=ctx.current_judgment.confidence_a,
                    confidence_opponent=ctx.current_judgment.confidence_b,
                    own_summary=ctx.combined_a[:400],
                    opponent_summary=ctx.combined_b[:400],
                    max_budget=ctx.decision_a.max_budget,
                )
                transcript.add_deliberation(
                    self.debater_b.name,
                    ctx.decision_b.bet_type.value,
                    ctx.decision_b.amount,
                    f"[Iter {ctx.iteration}] {ctx.decision_b.reasoning}",
                    include_context=True,
                    balance=balance_b,
                    confidence_self=ctx.current_judgment.confidence_b,
                    confidence_opponent=ctx.current_judgment.confidence_a,
                    own_summary=ctx.combined_b[:400],
                    opponent_summary=ctx.combined_a[:400],
                    max_budget=ctx.decision_b.max_budget,
                )

            
            # Check mutual PASS
            if ctx.decision_a.bet_type == BetType.PASS and ctx.decision_b.bet_type == BetType.PASS:
                ctx.pass_count_a += 1
                ctx.pass_count_b += 1
                ctx.termination_reason = "mutual_pass"
                ctx.iterations_completed = ctx.iteration
                break
            
            # Track pass counts for non-mutual PASS
            if ctx.decision_a.bet_type == BetType.PASS:
                ctx.pass_count_a += 1
            if ctx.decision_b.bet_type == BetType.PASS:
                ctx.pass_count_b += 1
            
            # Process bets for active participants
            if ctx.decision_a.bet_type != BetType.PASS:
                ctx.bet_count_a += 1
                ctx = self._process_bet(ctx, transcript, is_debater_a=True)
            
            if ctx.decision_b.bet_type != BetType.PASS:
                ctx.bet_count_b += 1
                ctx = self._process_bet(ctx, transcript, is_debater_a=False)
            
            # Re-evaluate with updated combined arguments
            # Pass ctx.current_judgment as prior so judge can penalize stagnation (Phase 3)
            self.judge.reset()
            try:
                new_judgment = self.judge.evaluate(
                    ctx.topic, ctx.combined_a, ctx.combined_b, ctx.round_id,
                    prior_judgment=ctx.current_judgment,
                )
                ctx.current_judgment = new_judgment
                
                if transcript:
                    transcript.add_judgment(
                        self.judge.name + f" (iter {ctx.iteration})",
                        ctx.current_judgment.reasoning,
                        ctx.current_judgment.confidence_a,
                        ctx.current_judgment.confidence_b,
                        sub_judgments=ctx.current_judgment.sub_judgments
                    )
            except ValueError as e:
                # Judge validation failed, keep previous judgment
                print(f"  [Warning] Judge validation failed iter {ctx.iteration}: {e}")
                if transcript:
                    transcript.add_judgment(
                        self.judge.name + f" (iter {ctx.iteration})",
                        f"[VALIDATION_FAILED] Keeping previous scores. Error: {str(e)[:100]}",
                        ctx.current_judgment.confidence_a,
                        ctx.current_judgment.confidence_b,
                        sub_judgments=None
                    )
            
            # Track confidence trajectory
            ctx.confidence_trajectory.append((
                ctx.iteration,
                ctx.current_judgment.confidence_a,
                ctx.current_judgment.confidence_b
            ))
            
            # Notify observers of iteration completion
            for observer in self.observers:
                if hasattr(observer, 'on_iteration'):
                    observer.on_iteration(ctx, ctx.iteration)
            
            ctx.iterations_completed = ctx.iteration
            
            prev_balance_a = self.ledger.balance(self.debater_a.name)
            prev_balance_b = self.ledger.balance(self.debater_b.name)
        
        # If we exited due to max iterations
        if not ctx.termination_reason:
            ctx.termination_reason = "max_iterations"
            ctx.iterations_completed = ctx.max_iterations
        
        return ctx
    
    def _process_bet(
        self,
        ctx: DynamicRoundContext,
        transcript: Optional["RoundTranscript"],
        is_debater_a: bool,
    ) -> DynamicRoundContext:
        """Process a single debater's bet and generate content."""
        debater = self.debater_a if is_debater_a else self.debater_b
        decision = ctx.decision_a if is_debater_a else ctx.decision_b
        opponent_combined = ctx.combined_b if is_debater_a else ctx.combined_a
        own_combined = ctx.combined_a if is_debater_a else ctx.combined_b
        own_summary = ctx.summary_a if is_debater_a else ctx.summary_b  # Use compressed memory
        conf_self = ctx.current_judgment.confidence_a if is_debater_a else ctx.current_judgment.confidence_b
        conf_opponent = ctx.current_judgment.confidence_b if is_debater_a else ctx.current_judgment.confidence_a
        
        # Calculate iteration-based fee (5% per iteration, cap at 50%)
        iteration_fee = min(0.05 * ctx.iteration, 0.50)
        
        # Place bet (deducts from balance, adds to locked pot)
        bet = self.betting.place_bet(
            debater.name, 
            decision.amount, 
            ctx.round_id, 
            self.ledger,
            custom_fee_rate=iteration_fee
        )
        if bet:
            ctx.all_bets.append(bet)
            ctx.locked_pot += bet.amount
            # Track bet amount for metrics
            if is_debater_a:
                ctx.total_bet_amount_a += decision.amount
            else:
                ctx.total_bet_amount_b += decision.amount
        
        current_bal = self.ledger.balance(debater.name)
        
        # Generate content
        if decision.bet_type == BetType.RESPOND:
            # Optionally run web search if the model opted in
            research_context = None
            if decision.use_search:
                tool = get_research_tool()
                search_query = f"{ctx.topic} {decision.reasoning[:50]}"
                search_result = tool.search(search_query)
                research_context = search_result.summary
                # Deduct dynamic search tool cost
                search_cost = search_result.token_cost
                self.ledger.deduct(debater.name, search_cost, "search_tool_cost", ctx.round_id)
                if is_debater_a:
                    ctx.gen_cost_a += search_cost
                else:
                    ctx.gen_cost_b += search_cost
            
            # Single unified generation call
            budget_llm_tokens = int(decision.max_budget * ctx.token_cost_ratio)
            response = debater.generate_argument(
                ctx.topic, ctx.round_id,
                opponent_argument=opponent_combined,
                own_history=own_summary or own_combined,
                research_context=research_context,
                current_balance=self.ledger.balance(debater.name),
                confidence_self=conf_self,
                confidence_opponent=conf_opponent,
                strategy_context=decision.reasoning,
                max_budget_tokens=budget_llm_tokens,
            )
            response.used_search = decision.use_search
            
            gen_cost = response.llm_tokens_used // ctx.token_cost_ratio
            if gen_cost > 0:
                self.ledger.deduct(debater.name, gen_cost, "generation_cost", ctx.round_id)
                if is_debater_a:
                    ctx.gen_cost_a += gen_cost
                else:
                    ctx.gen_cost_b += gen_cost
            response.tokens_bet = decision.amount
            ctx.all_counters.append(response)
            
            # Update combined argument and self-summarize
            label = f"[RESPOND+SEARCH iter={ctx.iteration}]" if decision.use_search else f"[RESPOND iter={ctx.iteration}]"
            if is_debater_a:
                ctx.combined_a += f"\n\n{label}\n{response.content}"
                summary_result = debater.summarize_position(ctx.combined_a)
                ctx.summary_a = summary_result.text
                summary_cost = summary_result.llm_tokens_used // ctx.token_cost_ratio
                if summary_cost > 0:
                    self.ledger.deduct(debater.name, summary_cost, "summarization_cost", ctx.round_id)
                    ctx.gen_cost_a += summary_cost
            else:
                ctx.combined_b += f"\n\n{label}\n{response.content}"
                summary_result = debater.summarize_position(ctx.combined_b)
                ctx.summary_b = summary_result.text
                summary_cost = summary_result.llm_tokens_used // ctx.token_cost_ratio
                if summary_cost > 0:
                    self.ledger.deduct(debater.name, summary_cost, "summarization_cost", ctx.round_id)
                    ctx.gen_cost_b += summary_cost
            
            if transcript:
                transcript.add_argument(
                    debater.name, response.content,
                    is_counter=True, tokens_bet=decision.amount
                )
        
        return ctx
    
    # ─────────────────────────────────────────────────────────────────────────
    # Phase 4: Final Distribution
    # ─────────────────────────────────────────────────────────────────────────
    
    def _phase_distribute_tokens(
        self, ctx: DynamicRoundContext, transcript: Optional["RoundTranscript"]
    ) -> DynamicRoundContext:
        """Final pot split based on current judgment."""
        dist = self.distributor.distribute_pot(
            self.debater_a.name,
            self.debater_b.name,
            ctx.current_judgment.confidence_a,
            ctx.current_judgment.confidence_b,
            ctx.round_id,
            self.ledger,
            extra_pot_tokens=ctx.locked_pot
        )
        
        ctx.tokens_awarded_a += dist.tokens_a
        ctx.tokens_awarded_b += dist.tokens_b
        
        if transcript:
            transcript.tokens_awarded_a += dist.tokens_a
            transcript.tokens_awarded_b += dist.tokens_b
            
            # Log bet resolutions for each debater
            # In dynamic mode, "winning" means final confidence > initial confidence
            bets_a = [b for b in ctx.all_bets if b.bettor_id == self.debater_a.name]
            bets_b = [b for b in ctx.all_bets if b.bettor_id == self.debater_b.name]
            
            # Determine winners
            won_a = ctx.current_judgment.confidence_a > ctx.initial_judgment.confidence_a
            won_b = ctx.current_judgment.confidence_b > ctx.initial_judgment.confidence_b
            
            # Resolve bets for debater A — convex (sqrt-shaped) reward curve:
            #   5pt improvement  → 1.07x  |  20pt → 2.00x  |  30pt → 2.73x  |  40pt+ → 3.00x cap
            for bet in bets_a:
                if won_a:
                    improvement_a = ctx.current_judgment.confidence_a - ctx.initial_judgment.confidence_a
                    multiplier = 1.0 + min(2.0, (max(0.0, improvement_a) * 10) ** 0.5)
                else:
                    multiplier = 1.0
                self.betting.resolve_bet(bet, won_a, multiplier, self.ledger)
            
            # Resolve bets for debater B (same convex curve)
            for bet in bets_b:
                if won_b:
                    improvement_b = ctx.current_judgment.confidence_b - ctx.initial_judgment.confidence_b
                    multiplier = 1.0 + min(2.0, (max(0.0, improvement_b) * 10) ** 0.5)
                else:
                    multiplier = 1.0
                self.betting.resolve_bet(bet, won_b, multiplier, self.ledger)
            
            # Log to transcript
            if bets_a:
                total_fee_a = sum(b.fee_paid for b in bets_a)
                transcript.add_bet_resolution(
                    self.debater_a.name, won_a, dist.tokens_a, fee_paid=total_fee_a
                )
            
            if bets_b:
                total_fee_b = sum(b.fee_paid for b in bets_b)
                transcript.add_bet_resolution(
                    self.debater_b.name, won_b, dist.tokens_b, fee_paid=total_fee_b
                )
        
        return ctx


    def _audit_round_accounting(self, ctx: DynamicRoundContext) -> None:
        """Audit round-level mint/burn invariants using ledger transactions."""
        txs = [t for t in self.ledger.get_history() if t.round_id == ctx.round_id]
        minted = sum(t.amount for t in txs if t.from_id is None and t.to_id is not None)
        burned = sum(t.amount for t in txs if t.from_id is not None and t.to_id is None)
        ctx.round_minted = minted
        ctx.round_burned = burned
        ctx.round_supply_end = sum(self.ledger.summary()["balances"].values())
        ctx.round_net_supply_change = ctx.round_supply_end - ctx.round_supply_start

        expected_net = minted - burned
        drift = abs(expected_net - ctx.round_net_supply_change)
        if drift > 0.01:
            ctx.accounting_ok = False
            ctx.accounting_notes.append(
                f"Supply drift: expected {expected_net:.4f}, observed {ctx.round_net_supply_change:.4f}"
            )

        if ctx.tokens_awarded_a < 0 or ctx.tokens_awarded_b < 0:
            ctx.accounting_ok = False
            ctx.accounting_notes.append("Negative token award detected.")
    
    # ─────────────────────────────────────────────────────────────────────────
    # Build Result
    # ─────────────────────────────────────────────────────────────────────────
    
    def _build_result(self, ctx: DynamicRoundContext, observation_reports: List = None) -> DynamicRoundResult:
        """Convert context to result."""
        return DynamicRoundResult(
            round_id=ctx.round_id,
            topic=ctx.topic,
            argument_a=ctx.arg_a,
            argument_b=ctx.arg_b,
            initial_judgment=ctx.initial_judgment,
            final_judgment=ctx.current_judgment,
            tokens_awarded_a=ctx.tokens_awarded_a,
            tokens_awarded_b=ctx.tokens_awarded_b,
            iterations_completed=ctx.iterations_completed,
            termination_reason=ctx.termination_reason,
            all_bets=ctx.all_bets,
            all_counters=ctx.all_counters,
            observation_reports=observation_reports or [],
        )
