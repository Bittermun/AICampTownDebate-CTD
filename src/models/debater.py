"""
Debater: LLM wrapper for generating debate arguments.
Supports: stub mode, llama-cpp-python, Ollama, vLLM, and OpenAI-compatible APIs.
"""
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from enum import Enum
import json
import re
import random

from src.prompting import RuleCard, load_rule_card, render_rule_view


class BetType(Enum):
    """Type of bet a debater can make."""
    PASS = "pass"       # No bet, save tokens
    RESPOND = "respond" # Respond to the debate (may optionally use search tool)


@dataclass
class BetDecision:
    """Result of a debater's betting decision."""
    bet_type: BetType
    amount: float  # 0 if PASS
    reasoning: str = ""  # LLM's strategic justification
    llm_tokens_used: int = 0  # Tokens consumed by deliberation LLM call
    max_budget: float = 30.0  # Max economic tokens to spend on generation
    use_search: bool = False  # Whether the model opted in to pay for a web search
    intent: str = "other"
    intent_mix: list[dict] | None = None
    rule_refs_used: list[str] | None = None
    rationale_short: str = ""
    action_label: str = ""



@dataclass
class DebaterConfig:
    model_path: str  # "stub", "ollama:model_name", or path to GGUF
    name: str
    system_prompt: Optional[str] = None
    gpu_layers: int = 20
    context_size: int = 4096
    ev_guard_enabled: bool = True
    ev_guard_min_ev: float = -0.20  # Loosened: losing debater needs room to try and recover
    ev_guard_edge_scale: float = 0.8
    low_balance_threshold: float = 60.0
    low_balance_bet_cap: float = 10.0
    strict_runtime: bool = True
    kelly_enabled: bool = True          # Use Kelly criterion for sizing (replaces LLM amount)
    kelly_scale: float = 0.5            # Fraction of edge to wager (0.5 = half-Kelly, more conservative)
    kelly_cap: float = 0.25             # Maximum fraction of balance to stake per bet
    verbosity_scale_enabled: bool = True  # Scale max_tokens with balance ratio
    verbosity_base_tokens: int = 600      # Baseline max tokens for generation
    initial_balance_ref: float = 200.0    # Reference balance (set to actual initial_balance at init)


@dataclass
class Argument:
    content: str
    debater_id: str
    round_id: int
    is_counter: bool = False
    used_search: bool = False  # True if the web search tool was called during generation
    tokens_bet: float = 0.0
    llm_tokens_used: int = 0  # Actual LLM tokens used (for cost tracking)
    thinking: str = ""  # Internal reasoning (hidden from judge/opponent, logged for analysis)


@dataclass
class PositionSummary:
    """Result of self-summarization for memory management."""
    text: str  # Compressed position summary
    llm_tokens_used: int = 0  # Tokens consumed (costs debater balance)


class Debater:
    """
    Wraps an LLM to participate in debates.
    Maintains persistent state (token balance, strategy memory).
    """
    
    def __init__(self, config: DebaterConfig):
        self.config = config
        self.name = config.name
        self._history: list[dict] = []
        
        # Determine backend
        if config.model_path == "stub" or config.model_path.startswith("stub:"):
            self._backend = "stub"
        elif config.model_path.startswith("ollama:"):
            self._backend = "ollama"
            self._ollama_model = config.model_path.split(":", 1)[1]
        elif config.model_path.startswith("vllm:"):
            self._backend = "vllm"
            self._vllm_model = config.model_path.split(":", 1)[1]
        elif config.model_path.startswith("openai:"):
            self._backend = "openai_compat"
            self._openai_model = config.model_path.split(":", 1)[1]
        else:
            self._backend = "llama_cpp"
        
        self._model = None
        self._ollama = None
        self._vllm = None
        self._openai = None
        self._rule_card: RuleCard | None = None
        self._rule_card_load_error: str = ""
        self._init_rule_card()

    def _init_rule_card(self) -> None:
        path = Path("configs/rule_cards/tournament_core_v1.yaml")
        if not path.exists():
            return
        try:
            self._rule_card = load_rule_card(str(path))
        except Exception as exc:
            self._rule_card_load_error = str(exc)

    def _rule_view_text(self, view_name: str) -> str:
        if not self._rule_card:
            return ""
        return render_rule_view(self._rule_card, view_name=view_name, max_rules=8, include_ids=True)
    
    def load_model(self):
        """Load the LLM. Call this before generating."""
        if self._backend == "stub":
            print(f"[{self.name}] Model loaded (stub)")
            return
        
        if self._backend == "ollama":
            from .ollama_backend import get_backend, OllamaConfig
            self._ollama = get_backend(OllamaConfig(model=self._ollama_model))
            if self._ollama.is_available():
                print(f"[{self.name}] Ollama connected: {self._ollama_model}")
            else:
                msg = f"[{self.name}] Ollama not available: {self._ollama_model}"
                if self.config.strict_runtime:
                    raise RuntimeError(msg)
                print(f"{msg}, falling back to stub")
                self._backend = "stub"
            return
        
        if self._backend == "vllm":
            from .vllm_backend import VLLMBackend, VLLMConfig
            self._vllm = VLLMBackend(VLLMConfig(model=self._vllm_model))
            if self._vllm.is_available():
                print(f"[{self.name}] vLLM connected: {self._vllm_model}")
            else:
                msg = f"[{self.name}] vLLM not available: {self._vllm_model}"
                if self.config.strict_runtime:
                    raise RuntimeError(msg)
                print(f"{msg}, falling back to stub")
                self._backend = "stub"
            return

        if self._backend == "openai_compat":
            from .openai_compat_backend import OpenAICompatBackend, OpenAICompatConfig
            self._openai = OpenAICompatBackend(OpenAICompatConfig(model=self._openai_model))
            if self._openai.is_available():
                print(f"[{self.name}] OpenAI-compatible endpoint connected: {self._openai_model}")
            else:
                msg = f"[{self.name}] OpenAI-compatible endpoint not available: {self._openai_model}"
                if self.config.strict_runtime:
                    raise RuntimeError(msg)
                print(f"{msg}, falling back to stub")
                self._backend = "stub"
            return
        
        try:
            from llama_cpp import Llama
            self._model = Llama(
                model_path=self.config.model_path,
                n_gpu_layers=self.config.gpu_layers,
                n_ctx=self.config.context_size,
                verbose=False,
            )
            print(f"[{self.name}] Model loaded: {self.config.model_path}")
        except ImportError:
            msg = f"[{self.name}] llama-cpp-python not installed"
            if self.config.strict_runtime:
                raise RuntimeError(msg)
            print(f"{msg}, using stub")
            self._backend = "stub"

    def _generate(self, prompt: str, system: Optional[str] = None, max_tokens: int = 512, json_mode: bool = False, temperature: float = 0.8) -> "GenerationResult":
        """Unified sync generation call."""
        if self._backend == "ollama":
            return self._ollama.generate(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode, temperature=temperature)
        elif self._backend == "vllm":
            return self._vllm.generate(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode, temperature=temperature)
        elif self._backend == "openai_compat":
            return self._openai.generate(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode, temperature=temperature)
        else:
            # Fallback for stub/llama_cpp (simplified)
            from .ollama_backend import GenerationResult
            if self._backend == "stub":
                return GenerationResult(text=f"[STUB] Response to: {prompt[:50]}...", tokens_used=0)
            else:
                output = self._model(
                    f"{system}\n\n{prompt}" if system else prompt,
                    max_tokens=max_tokens,
                    stop=["</s>", "\n\n\n"],
                    echo=False,
                    temperature=temperature,
                )
                return GenerationResult(text=output["choices"][0]["text"].strip(), tokens_used=0)

    async def _generate_async(self, prompt: str, system: Optional[str] = None, max_tokens: int = 512, json_mode: bool = False, temperature: float = 0.8) -> "GenerationResult":
        """Unified async generation call."""
        if self._backend == "ollama":
            return await self._ollama.generate_async(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode, temperature=temperature)
        elif self._backend == "vllm":
            return await self._vllm.generate_async(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode, temperature=temperature)
        elif self._backend == "openai_compat":
            return await self._openai.generate_async(prompt, system=system, max_tokens=max_tokens, json_mode=json_mode, temperature=temperature)
        else:
            return self._generate(prompt, system, max_tokens, json_mode, temperature)
    
    def generate_argument(
        self,
        topic: str,
        round_id: int,
        opponent_argument: Optional[str] = None,
        own_history: Optional[str] = None,  # Debater's own past statements
        research_context: Optional[str] = None, # Optional web search results
        current_balance: Optional[float] = None,
        confidence_self: Optional[float] = None,
        confidence_opponent: Optional[float] = None,
        strategy_context: Optional[str] = None,
        max_budget_tokens: Optional[int] = None,
    ) -> Argument:
        """
        Generate an argument on the given topic.
        If opponent_argument is provided, this is a counter-argument.
        If own_history is provided, debater sees their past statements for consistency.
        If research_context is provided, integrates web search results.
        If current_balance is provided, inject token-aware economy info.
        If confidence scores are provided, model sees current standing.
        """
        is_counter = opponent_argument is not None
        
        # Build tournament-aware system prompt (facts only, no strategy guidance)
        base_prompt = self.config.system_prompt or ""
        
        # Tournament context: pure facts, let the model strategize
        tournament_facts = []
        tournament_facts.append("TOURNAMENT: This is one round of many. Your tokens persist across rounds.")
        tournament_facts.append("ELIMINATION: Balance ≤ 0 = disqualified from the tournament.")
        if current_balance is not None:
            tournament_facts.append(f"BALANCE: {current_balance:.0f} tokens")
        
        if confidence_self is not None and confidence_opponent is not None:
            tournament_facts.append(f"STANDING: You={confidence_self:.0%} vs Other AI={confidence_opponent:.0%}")
        
        tournament_facts.append("OBJECTIVE: Maximize expected final tournament balance, not single-turn style points.")
        tournament_facts.append("COSTS: All actions cost tokens; longer outputs typically cost more.")
        tournament_facts.append("BETTING: Total bet cost = stake + fee. HOLD avoids bet stake/fee.")

        economy_info = "\n\n=== SITUATION ===\n" + "\n".join(tournament_facts)
        rules_view = self._rule_view_text("generation_compact")
        if rules_view:
            economy_info += "\n\n=== RULE CARD ===\n" + rules_view
        system = base_prompt + economy_info
        
        # Build prompt - include own history for consistency
        # Add thinking instruction (autonomy-allowing)
        thinking_instruction = "\n\nYou may use <thinking></thinking> tags to reason privately first."
        
        parts = [f"Topic: {topic}"]
        
        if own_history:
            history_snippet = own_history[-500:] if len(own_history) > 500 else own_history
            parts.append(f"Your previous context:\n{history_snippet}")
            
        if research_context:
            parts.append(f"Factual research to support your response:\n{research_context}")
            
        if opponent_argument:
            parts.append(f"Other AI's statement:\n{opponent_argument}")
            
        if strategy_context:
            parts.append(f"Your strategic plan for this response:\n{strategy_context}")
            
        parts.append(f"{thinking_instruction}\n\nYour response:")
        
        prompt = "\n\n".join(parts)
        
        # Store balance for verbosity scaling
        self._current_balance = current_balance
        # Determine strict generation limit
        if self.config.verbosity_scale_enabled and hasattr(self, '_current_balance') and self._current_balance is not None:
            bal_ratio = self._current_balance / max(self.config.initial_balance_ref, 1.0)
            scale = max(0.3, min(1.5, bal_ratio))  # clamp: 0.3x (bankrupt) → 1.5x (flush)
            effective_max = int((max_budget_tokens or self.config.verbosity_base_tokens) * scale)
        else:
            effective_max = max_budget_tokens or self.config.verbosity_base_tokens
        
        # Generate based on backend
        result = self._generate(prompt, system=system, max_tokens=effective_max)
        response_text = result.text
        llm_tokens_used = result.tokens_used
        
        # Extract thinking (if present) before returning
        import re
        thinking = ""
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', response_text, re.DOTALL)
        if thinking_match:
            thinking = thinking_match.group(1).strip()
            # Remove thinking from visible content
            response_text = re.sub(r'<thinking>.*?</thinking>', '', response_text, flags=re.DOTALL).strip()
        
        return Argument(
            content=response_text,
            debater_id=self.name,
            round_id=round_id,
            is_counter=is_counter,
            llm_tokens_used=llm_tokens_used,
            thinking=thinking,
        )
    
    async def generate_argument_async(
        self,
        topic: str,
        round_id: int,
        current_balance: Optional[float] = None,
    ) -> Argument:
        """Async version of generate_argument for parallel initial arguments.
        
        Simplified for initial arguments only (no opponent_argument or history).
        Uses async backend for non-blocking generation.
        """
        if self._backend not in ["ollama", "vllm"]:
            # Fallback to sync for non-api backends
            return self.generate_argument(topic, round_id, current_balance=current_balance)
        
        # Build system prompt (same as sync version)
        base_prompt = self.config.system_prompt or ""
        tournament_facts = [
            "TOURNAMENT: This is one round of many. Your tokens persist across rounds.",
            "ELIMINATION: Balance ≤ 0 = disqualified from the tournament.",
        ]
        if current_balance is not None:
            tournament_facts.append(f"BALANCE: {current_balance:.0f} tokens")
        tournament_facts.append("COSTS: All actions cost tokens. Longer responses cost more.")
        tournament_facts.append("BETTING: Fees start at 5% and increase each iteration. HOLD costs nothing.")

        economy_info = "\n\n=== SITUATION ===\n" + "\n".join(tournament_facts)
        rules_view = self._rule_view_text("generation_compact")
        if rules_view:
            economy_info += "\n\n=== RULE CARD ===\n" + rules_view
        system = base_prompt + economy_info
        prompt = f"Topic: {topic}\n\nYour statement:"
        
        # Async generation
        result = await self._generate_async(prompt, system=system, max_tokens=600)
        
        return Argument(
            content=result.text,
            debater_id=self.name,
            round_id=round_id,
            is_counter=False,
            llm_tokens_used=result.tokens_used,
        )

    def generate_research(
        self,
        topic: str,
        round_id: int,
        own_argument: str,
        current_balance: Optional[float] = None,
        confidence_self: Optional[float] = None,
        confidence_opponent: Optional[float] = None,
    ) -> Argument:
        """Generate a factual research-based response.
        
        Model is encouraged to provide evidence and citations.
        """
        system = "You are a research AI. Provide factual, evidence-based claims with clear reasoning."
        
        tournament_facts = []
        if current_balance is not None:
            tournament_facts.append(f"CURRENT BALANCE: {current_balance:.0f} tokens")
        if confidence_self is not None and confidence_opponent is not None:
            tournament_facts.append(f"STANDING: You={confidence_self:.0%} vs Opponent={confidence_opponent:.0%}")
            
        research_prompt = f"""Topic: {topic}
Your current position:
{own_argument[:500]}

TASK: Provide the strongest factual evidence to support your position or refute counter-claims.
Include thinking tags <thinking></thinking> if you have multiple options.

Research synthesis:"""

        if tournament_facts:
            system += "\n\nSITUATION:\n" + "\n".join(tournament_facts)

        result = self._generate(research_prompt, system=system, max_tokens=400)
        
        # Extract thinking
        thinking = ""
        text = result.text
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', text, re.DOTALL)
        if thinking_match:
            thinking = thinking_match.group(1).strip()
            text = re.sub(r'<thinking>.*?</thinking>', '', text, flags=re.DOTALL).strip()

        return Argument(
            content=text,
            debater_id=self.name,
            round_id=round_id,
            is_counter=True,
            llm_tokens_used=result.tokens_used,
            thinking=thinking
        )
    

    def summarize_position(self, full_history: str) -> PositionSummary:
        """
        Self-summarize position for memory management.
        
        Compresses full argument history into key claims and strongest evidence.
        This costs tokens (thinking isn't free) but prevents context bloat.
        
        Args:
            full_history: Combined argument text accumulated so far
            
        Returns:
            PositionSummary with compressed text and token cost
        """
        if len(full_history) < 400:
            # No need to summarize short histories
            return PositionSummary(text=full_history, llm_tokens_used=0)
        
        prompt = (
            f"This is your past context from this debate. "
            f"Compress to what you might want to remember (80 words max).\n\n"
            f"Your statements:\n{full_history[:1500]}\n\n"
            f"Remember:"
        )
        
        system = "Compress for future reference. Keep what seems useful."
        
        # Generate summary
        result = self._generate(prompt, system=system, max_tokens=120)
        summary_text = result.text.strip()
        llm_tokens_used = result.tokens_used
        
        return PositionSummary(text=summary_text, llm_tokens_used=llm_tokens_used)
    
    def decide_bet(
        self,
        balance: float,
        opponent_argument: str,
        own_argument: str,
        confidence_self: float = 0.5,
        confidence_opponent: float = 0.5,
        balance_change: Optional[float] = None,
        current_fee_rate: float = 0.05,
        last_judgment_reasoning: Optional[str] = None,
        balance_history: Optional[list] = None,  # Past balance values for trend signal
    ) -> BetDecision:
        """
        LLM-driven deliberation: model decides whether to RESPOND or HOLD.
        Returns BetDecision with type, amount, and reasoning.
        confidence_self/opponent are judge scores (debaters see scores but not reasoning).
        """
        # Cannot bet if balance too low
        if balance <= 20:
            return BetDecision(bet_type=BetType.PASS, amount=0, reasoning="Balance too low to bet.", action_label="HOLD")
        
        # For stub mode, use heuristic fallback
        if self._backend == "stub":
            # Economic heuristic for stub mode to preserve realistic PASS behavior.
            edge = confidence_self - confidence_opponent
            est_p = max(0.05, min(0.95, 0.5 + self.config.ev_guard_edge_scale * edge))
            ev_per_stake = (2 * est_p) - 1 - current_fee_rate
            if self.config.ev_guard_enabled and (ev_per_stake < self.config.ev_guard_min_ev or balance < 40):
                return BetDecision(
                    bet_type=BetType.PASS,
                    amount=0,
                    reasoning=f"[STUB_EV_PASS] ev={ev_per_stake:.3f}, fee={current_fee_rate:.2f}",
                    use_search=False,
                    action_label="HOLD",
                )
            if random.random() < 0.3:
                return BetDecision(
                    bet_type=BetType.RESPOND,
                    amount=10,
                    reasoning="[STUB] Random respond/search choice",
                    use_search=True,
                    action_label="RESPOND",
                )
            return BetDecision(
                bet_type=BetType.RESPOND,
                amount=10,
                reasoning="[STUB] Random respond choice",
                use_search=False,
                action_label="RESPOND",
            )
        
        # LLM-driven deliberation prompt (facts only, no strategy hints)
        max_bet = min(20, balance * 0.3)
        
        feedback_str = ""
        if balance_change is not None and balance_change < 0:
            feedback_str = f"\n- LAST TURN: You spent/lost {abs(balance_change):.0f} tokens. Your balance DROPPED."
        judgment_line = ""
        if last_judgment_reasoning:
            # Extract allocation numbers if present (format: [ALLOC] Acc: A=X%/B=Y%, ...)
            judgment_line = f"\n- Last judgment: {last_judgment_reasoning[:150]}"
        # Balance trend signal
        trend_line = ""
        if balance_history and len(balance_history) >= 2:
            window = balance_history[-3:] if len(balance_history) >= 3 else balance_history
            delta = window[-1] - window[0]
            direction = "losing" if delta < -5 else ("gaining" if delta > 5 else "steady")
            trend_line = f"\n- Balance trend: {delta:+.0f} over last {len(window)} rounds ({direction})"
            
        rules_view = self._rule_view_text("deliberation_compact")
        rules_block = f"\n\nRULE CARD:\n{rules_view}" if rules_view else ""
        deliberation_prompt = f"""CONTEXT:
- This is one round of many. Tokens persist.
- Balance ≤ 0 = eliminated.

STATUS:
- Balance: {balance:.0f} tokens{feedback_str}
- Standing: You={confidence_self:.0%} vs Other AI={confidence_opponent:.0%}
- Costs: Variable based on response length. Current fee: {current_fee_rate:.0%}.
- Objective: maximize expected final balance over the tournament.{judgment_line}{trend_line}

Your statement:
{own_argument[:300]}

Other AI's statement:
{opponent_argument[:300]}

OPTIONS: RESPOND | HOLD

THINK FIRST in <thinking> tags. Reason about your ECONOMIC situation:
- How many tokens can you afford to spend?
- Is expected value positive after fee and generation cost?
- What is the minimum effective response?
- Is search worth paying for in this spot? (use_search=true has extra token cost)

Then respond JSON:
{{
  "reasoning": "...",
  "rationale_short": "...",
  "decision": "RESPOND|HOLD",
  "action": "RESPOND|HOLD",
  "intent": "claim|investigate|challenge|revise|other",
  "intent_mix": [{{"intent": "claim", "weight": 1.0}}],
  "rule_refs_used": ["R_BANKRUPTCY"],
  "amount": 0-{max_bet:.0f},
  "max_budget": 10-50,
  "use_search": true|false
}}

max_budget = maximum tokens you authorize spending on your response. Lower = cheaper but shorter.
use_search = whether to pay for a web search to support your argument (costs extra tokens).{rules_block}"""

        system = "Think step-by-step in <thinking> tags, then output valid JSON only."
        
        llm_tokens_used = 0
        try:
            # Deliberate
            # No json_mode - allow thinking tags before JSON
            result = self._generate(deliberation_prompt, system=system, max_tokens=250, json_mode=False)
            response = result.text
            llm_tokens_used = result.tokens_used
                
            # Parse response with Pydantic
            decision = self._parse_deliberation(response, balance, llm_tokens_used)
            if not self.config.ev_guard_enabled:
                return decision
            return self._enforce_economic_sanity(
                decision=decision,
                balance=balance,
                confidence_self=confidence_self,
                confidence_opponent=confidence_opponent,
                current_fee_rate=current_fee_rate,
            )
        except Exception as e:
            # Fallback to PASS on error (safe default)
            return BetDecision(
                bet_type=BetType.PASS,
                amount=0,
                reasoning=f"Fallback due to error: {e}",
                llm_tokens_used=llm_tokens_used,
                action_label="HOLD",
            )

    
    def _parse_deliberation(self, response: str, balance: float, llm_tokens_used: int = 0) -> BetDecision:
        """Parse LLM deliberation response with Pydantic validation.
        
        Extracts <thinking> tags for ITMC analysis before parsing JSON decision.
        """
        from pydantic import ValidationError
        from .response_models import DeliberationResponse
        
        # Extract thinking (ITMC) before JSON parsing
        thinking = ""
        thinking_match = re.search(r'<thinking>(.*?)</thinking>', response, re.DOTALL)
        if thinking_match:
            thinking = thinking_match.group(1).strip()
        
        # Remove thinking tags before JSON extraction
        json_response = re.sub(r'<thinking>.*?</thinking>', '', response, flags=re.DOTALL).strip()
        
        try:
            # Try direct Pydantic parse
            parsed = DeliberationResponse.model_validate_json(json_response)
            action_raw = (parsed.action or parsed.decision).upper()
            decision = "PASS" if action_raw == "HOLD" else parsed.decision.upper()
            # Kelly criterion bet sizing: f* = edge * kelly_scale, capped at kelly_cap * balance
            if self.config.kelly_enabled and parsed.decision.upper() == "RESPOND":
                edge = max(0.0, confidence_self - 0.5)
                kelly_f = edge * self.config.kelly_scale
                kelly_amount = kelly_f * balance
                amount = min(kelly_amount, self.config.kelly_cap * balance, balance * 0.3, 20)
                amount = max(amount, 1.0)  # floor: never bet 0 when RESPOND
            else:
                amount = min(parsed.amount, balance * 0.3, 20)
            max_budget = parsed.max_budget
            use_search = parsed.use_search
            intent = (parsed.intent or "other").lower()
            intent_mix = parsed.intent_mix
            rule_refs_used = parsed.rule_refs_used
            rationale_short = parsed.rationale_short or ""
            action_label = "HOLD" if decision == "PASS" else "RESPOND"
            
            # Combine thinking with reasoning
            full_reasoning = f"[THINKING] {thinking}\n[DECISION] {parsed.reasoning}" if thinking else parsed.reasoning
            
            if decision == 'PASS':
                return BetDecision(
                    bet_type=BetType.PASS,
                    amount=0,
                    reasoning=full_reasoning,
                    llm_tokens_used=llm_tokens_used,
                    max_budget=0.0,
                    intent=intent,
                    intent_mix=intent_mix,
                    rule_refs_used=rule_refs_used,
                    rationale_short=rationale_short,
                    action_label=action_label,
                )
            else:  # RESPOND
                return BetDecision(
                    bet_type=BetType.RESPOND,
                    amount=amount,
                    reasoning=full_reasoning,
                    llm_tokens_used=llm_tokens_used,
                    max_budget=max_budget,
                    use_search=use_search,
                    intent=intent,
                    intent_mix=intent_mix,
                    rule_refs_used=rule_refs_used,
                    rationale_short=rationale_short,
                    action_label=action_label,
                )
                
        except ValidationError:
            # Fallback: try to extract JSON from text
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                try:
                    parsed = DeliberationResponse.model_validate_json(json_match.group())
                    action_raw = (parsed.action or parsed.decision).upper()
                    decision = "PASS" if action_raw == "HOLD" else parsed.decision.upper()
                    # Kelly criterion bet sizing
                    if self.config.kelly_enabled and parsed.decision.upper() == "RESPOND":
                        edge = max(0.0, confidence_self - 0.5)
                        kelly_f = edge * self.config.kelly_scale
                        kelly_amount = kelly_f * balance
                        amount = min(kelly_amount, self.config.kelly_cap * balance, balance * 0.3, 20)
                        amount = max(amount, 1.0)
                    else:
                        amount = min(parsed.amount, balance * 0.3, 20)
                    max_budget = parsed.max_budget
                    use_search = parsed.use_search
                    intent = (parsed.intent or "other").lower()
                    intent_mix = parsed.intent_mix
                    rule_refs_used = parsed.rule_refs_used
                    rationale_short = parsed.rationale_short or ""
                    action_label = "HOLD" if decision == "PASS" else "RESPOND"
                    
                    if decision == 'PASS':
                        return BetDecision(
                            bet_type=BetType.PASS,
                            amount=0,
                            reasoning=parsed.reasoning,
                            llm_tokens_used=llm_tokens_used,
                            max_budget=0.0,
                            intent=intent,
                            intent_mix=intent_mix,
                            rule_refs_used=rule_refs_used,
                            rationale_short=rationale_short,
                            action_label=action_label,
                        )
                    else:  # RESPOND
                        return BetDecision(
                            bet_type=BetType.RESPOND,
                            amount=amount,
                            reasoning=parsed.reasoning,
                            llm_tokens_used=llm_tokens_used,
                            max_budget=max_budget,
                            use_search=use_search,
                            intent=intent,
                            intent_mix=intent_mix,
                            rule_refs_used=rule_refs_used,
                            rationale_short=rationale_short,
                            action_label=action_label,
                        )
                except ValidationError:
                    pass
            
            # Last-resort: check if action/decision present as bare keys before giving up
            bare_action = re.search(r'"(?:action|decision)"\s*:\s*"(RESPOND|HOLD|PASS)"'  , response, re.IGNORECASE)
            if bare_action:
                act = bare_action.group(1).upper()
                bet_type = BetType.PASS if act in ("HOLD", "PASS") else BetType.RESPOND
                return BetDecision(
                    bet_type=bet_type,
                    amount=10 if bet_type == BetType.RESPOND else 0,
                    reasoning=f"[PARTIAL_PARSE] Recovered action={act} from partial JSON",
                    llm_tokens_used=llm_tokens_used,
                    action_label=act if act != "PASS" else "HOLD",
                )
            # Final fallback: PASS is safer than random action
            fallback_reasoning = f"[THINKING] {thinking}\n[VALIDATION_FAILED] Defaulting to HOLD" if thinking else f"[VALIDATION_FAILED] Defaulting to HOLD (Raw: {response[:100]}...)"
            return BetDecision(
                bet_type=BetType.PASS,
                amount=0,
                reasoning=fallback_reasoning,
                llm_tokens_used=llm_tokens_used,
                max_budget=0.0,
                action_label="HOLD",
            )

    def _enforce_economic_sanity(
        self,
        decision: BetDecision,
        balance: float,
        confidence_self: float,
        confidence_opponent: float,
        current_fee_rate: float,
    ) -> BetDecision:
        """Post-process deliberation with a lightweight EV sanity check.
        
        Prevents pathological always-RESPOND behavior when expected value is strongly negative.
        """
        if decision.bet_type != BetType.RESPOND:
            return decision
        
        edge = confidence_self - confidence_opponent
        est_p = max(0.05, min(0.95, 0.5 + self.config.ev_guard_edge_scale * edge))
        ev_per_stake = (2 * est_p) - 1 - current_fee_rate
        
        # If EV is strongly negative, conserve budget unless model has very strong edge.
        if ev_per_stake < self.config.ev_guard_min_ev:
            return BetDecision(
                bet_type=BetType.PASS,
                amount=0,
                reasoning=f"[EV_GUARD_PASS] ev={ev_per_stake:.3f}, edge={edge:.3f}, fee={current_fee_rate:.2f}. {decision.reasoning}",
                llm_tokens_used=decision.llm_tokens_used,
                max_budget=0.0,
                use_search=False,
                intent=decision.intent,
                intent_mix=decision.intent_mix,
                rule_refs_used=decision.rule_refs_used,
                rationale_short=decision.rationale_short,
                action_label="HOLD",
            )
        
        # Capital preservation: avoid oversized bets when balance is getting tight.
        if balance < self.config.low_balance_threshold and decision.amount > self.config.low_balance_bet_cap:
            decision.amount = self.config.low_balance_bet_cap
            decision.reasoning = (
                f"[CAP_PRESERVE] bet_capped_to_{self.config.low_balance_bet_cap:.0f}"
                f"_at_balance_{balance:.0f}. {decision.reasoning}"
            )
        
        return decision

    
    def unload_model(self):
        """Free model from memory."""
        self._model = None
        self._ollama = None
        self._vllm = None
        self._openai = None
        print(f"[{self.name}] Model unloaded")
