"""
Observers: Passive analytics components that track debate dynamics.

Observers implement the Observer protocol and are called during dynamic debates.
They do NOT affect scoring - only observe and report.
"""
from dataclasses import dataclass, field
from typing import Protocol, Optional, List, Dict, Any, TYPE_CHECKING
import json

if TYPE_CHECKING:
    from .dynamic_round import DynamicRoundContext


@dataclass
class ObservationReport:
    """Output from an observer."""
    observer_name: str
    metrics: Dict[str, Any] = field(default_factory=dict)
    narrative: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "observer": self.observer_name,
            "metrics": self.metrics,
            "narrative": self.narrative,
        }


class Observer(Protocol):
    """Protocol for debate observers."""
    
    @property
    def name(self) -> str:
        """Unique name for this observer."""
        ...
    
    def on_iteration(self, ctx: "DynamicRoundContext", iteration: int) -> None:
        """Called after each betting iteration."""
        ...
    
    def finalize(self, ctx: "DynamicRoundContext") -> ObservationReport:
        """Called after distribution. Returns final report."""
        ...


class MetricsObserver:
    """
    Computes debate metrics without LLM calls.
    
    Curated metrics:
    - efficiency: tokens_awarded / gen_cost (None if 0)
    - aggression: bet_count / iterations
    - pass_rate: pass_count / iterations
    - momentum_shifts: lead changes > 5%
    - final_lead: winner's confidence margin
    - elapsed_seconds: total wall-clock time
    """
    
    MOMENTUM_THRESHOLD = 0.05  # 5% change = significant lead shift
    
    def __init__(self):
        self._prev_leader: Optional[str] = None
        self._momentum_shifts: int = 0
        self._start_time: float = 0.0  # Will set on first iteration
        self._timing_started: bool = False
        self._iteration_times: List[float] = []
        self._economy_mentions_a: int = 0
        self._economy_mentions_b: int = 0
        self._economy_keywords = {"token", "tokens", "cost", "costs", "fee", "fees", "balance", "spend", "spent", "budget", "payout", "multiplier", "bankrupt"}
    
    @property
    def name(self) -> str:
        return "MetricsObserver"
    
    def on_iteration(self, ctx: "DynamicRoundContext", iteration: int) -> None:
        """Track momentum shifts and timing during debate."""
        import time
        
        # Start timing on first actual iteration
        if not self._timing_started:
            self._start_time = time.time()
            self._timing_started = True
        
        self._iteration_times.append(time.time() - self._start_time)
        
        if ctx.current_judgment is None:
            return
        
        conf_a = ctx.current_judgment.confidence_a
        conf_b = ctx.current_judgment.confidence_b
        
        # Determine current leader (with threshold)
        if conf_a > conf_b + self.MOMENTUM_THRESHOLD:
            current_leader = "A"
        elif conf_b > conf_a + self.MOMENTUM_THRESHOLD:
            current_leader = "B"
        else:
            current_leader = "TIE"
        
        # Check for lead change
        if self._prev_leader is not None and current_leader != self._prev_leader:
            if self._prev_leader != "TIE" and current_leader != "TIE":
                self._momentum_shifts += 1
        
        self._prev_leader = current_leader
        
        # Check economy mentions in thinking
        if ctx.decision_a and ctx.decision_a.reasoning:
            reasoning_lower = ctx.decision_a.reasoning.lower()
            if any(word in reasoning_lower for word in self._economy_keywords):
                self._economy_mentions_a += 1
                
        if ctx.decision_b and ctx.decision_b.reasoning:
            reasoning_lower = ctx.decision_b.reasoning.lower()
            if any(word in reasoning_lower for word in self._economy_keywords):
                self._economy_mentions_b += 1
    
    def finalize(self, ctx: "DynamicRoundContext") -> ObservationReport:
        """Compute final metrics."""
        import time
        iterations = ctx.iterations_completed or 1  # Avoid div by 0

        # Balance deltas must be ledger-grounded, never reconstructed from proxies.
        final_balance_a = ctx.final_balance_a
        final_balance_b = ctx.final_balance_b
        net_change_a = final_balance_a - ctx.initial_balance_a
        net_change_b = final_balance_b - ctx.initial_balance_b

        outflow_a = 0.0
        inflow_a = 0.0
        outflow_b = 0.0
        inflow_b = 0.0
        if ctx.ledger is not None:
            txs = [t for t in ctx.ledger.get_history() if t.round_id == ctx.round_id]
            for t in txs:
                if t.from_id == ctx.debater_a_id:
                    outflow_a += t.amount
                if t.from_id == ctx.debater_b_id:
                    outflow_b += t.amount
                if t.to_id == ctx.debater_a_id:
                    inflow_a += t.amount
                if t.to_id == ctx.debater_b_id:
                    inflow_b += t.amount

        # Robust fallback when observer cannot map IDs from ledger.
        if outflow_a == 0 and inflow_a == 0 and outflow_b == 0 and inflow_b == 0:
            outflow_a = ctx.gen_cost_a + ctx.total_bet_amount_a
            outflow_b = ctx.gen_cost_b + ctx.total_bet_amount_b
            inflow_a = ctx.tokens_awarded_a
            inflow_b = ctx.tokens_awarded_b

        # ROI: net / outflow (negative ROI = net loss)
        roi_a = net_change_a / outflow_a if outflow_a > 0 else None
        roi_b = net_change_b / outflow_b if outflow_b > 0 else None
        
        # Aggression: bet frequency
        aggression_a = ctx.bet_count_a / iterations
        aggression_b = ctx.bet_count_b / iterations
        
        # Pass rate
        pass_rate_a = ctx.pass_count_a / iterations
        pass_rate_b = ctx.pass_count_b / iterations
        
        # Final lead
        if ctx.current_judgment:
            final_lead = abs(ctx.current_judgment.confidence_a - ctx.current_judgment.confidence_b)
            winner = "A" if ctx.current_judgment.confidence_a > ctx.current_judgment.confidence_b else "B"
        else:
            final_lead = 0.0
            winner = "TIE"
        
        metrics = {
            "iterations": iterations,
            "termination": ctx.termination_reason,
            "debater_a": {
                "net_change": round(net_change_a, 1),
                "roi": round(roi_a, 3) if roi_a is not None else None,
                "aggression": round(aggression_a, 3),
                "pass_rate": round(pass_rate_a, 3),
                "bet_count": ctx.bet_count_a,
                "gen_cost": ctx.gen_cost_a,
                "total_bet": ctx.total_bet_amount_a,
                "tokens_awarded": ctx.tokens_awarded_a,
                "outflow": round(outflow_a, 1),
                "inflow": round(inflow_a, 1),
                "validation_fallbacks": ctx.validation_fallback_a,
                "economy_mentions": self._economy_mentions_a,
            },
            "debater_b": {
                "net_change": round(net_change_b, 1),
                "roi": round(roi_b, 3) if roi_b is not None else None,
                "aggression": round(aggression_b, 3),
                "pass_rate": round(pass_rate_b, 3),
                "bet_count": ctx.bet_count_b,
                "gen_cost": ctx.gen_cost_b,
                "total_bet": ctx.total_bet_amount_b,
                "tokens_awarded": ctx.tokens_awarded_b,
                "outflow": round(outflow_b, 1),
                "inflow": round(inflow_b, 1),
                "validation_fallbacks": ctx.validation_fallback_b,
                "economy_mentions": self._economy_mentions_b,
            },
            "momentum_shifts": self._momentum_shifts,
            "final_lead": round(final_lead, 3),
            "winner": winner,
            "accounting_ok": ctx.accounting_ok,
            "accounting_notes": ctx.accounting_notes,
            "round_supply_start": round(ctx.round_supply_start, 3),
            "round_supply_end": round(ctx.round_supply_end, 3),
            "round_minted": round(ctx.round_minted, 3),
            "round_burned": round(ctx.round_burned, 3),
            "round_net_supply_change": round(ctx.round_net_supply_change, 3),
            "confidence_trajectory": ctx.confidence_trajectory,
            "elapsed_seconds": round(time.time() - self._start_time, 1) if self._timing_started else 0,
            "avg_seconds_per_iter": round((time.time() - self._start_time) / iterations, 1) if self._timing_started else 0,
        }
        
        # Narrative with net change
        narrative = f"{iterations} iters, {self._momentum_shifts} shifts, A:{net_change_a:+.0f} B:{net_change_b:+.0f}, winner: {winner}"
        
        return ObservationReport(
            observer_name=self.name,
            metrics=metrics,
            narrative=narrative,
        )
    
    def save(self, path: str) -> None:
        """Save accumulated metrics to JSON file.
        
        Note: This saves the last finalized report's metrics.
        Should be called after finalize() has been invoked.
        """
        # Build a summary from internal state
        data = {
            "observer": self.name,
            "momentum_shifts": self._momentum_shifts,
            "timing_started": self._timing_started,
            "iteration_times": self._iteration_times,
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)


class ScribeObserver:
    """
    LLM-based observer that generates incremental narrative summaries.
    
    Uses rolling summarization to keep context bounded:
    Input = (prev_summary + new_content_this_iteration)
    Output = updated_summary
    """
    
    def __init__(self, backend=None, debater_a_name: str = "A", debater_b_name: str = "B"):
        self._backend = backend
        self._debater_a_name = debater_a_name
        self._debater_b_name = debater_b_name
        self._running_summary: str = ""
        self._iteration_notes: List[str] = []
    
    @property
    def name(self) -> str:
        return "ScribeObserver"
    
    def on_iteration(self, ctx: "DynamicRoundContext", iteration: int) -> None:
        """Generate incremental summary for this iteration."""
        if self._backend is None:
            # No backend, just note the iteration
            self._iteration_notes.append(f"Iter {iteration}: decisions made")
            return
        
        # Build increment description
        action_a = ctx.decision_a.bet_type.value if ctx.decision_a else "unknown"
        action_b = ctx.decision_b.bet_type.value if ctx.decision_b else "unknown"
        conf_a = ctx.current_judgment.confidence_a if ctx.current_judgment else 0.5
        conf_b = ctx.current_judgment.confidence_b if ctx.current_judgment else 0.5
        
        new_content = f"Iter {iteration}: {self._debater_a_name} chose {action_a}, {self._debater_b_name} chose {action_b}. Scores: {conf_a:.0%} vs {conf_b:.0%}."
        
        # Generate incremental summary
        prompt = f"""You are a debate Scribe. Summarize the debate's evolution.

Previous summary:
{self._running_summary or "(Debate just started)"}

New development:
{new_content}

Write 1-2 sentences updating the summary. Focus on strategic shifts, pivots, and momentum changes."""
        
        try:
            result = self._backend.generate(prompt, system="You are a concise analyst.", max_tokens=100)
            self._running_summary = result.text.strip()
        except Exception:
            # Fallback: just append the note
            self._running_summary += f" {new_content}"
        
        self._iteration_notes.append(new_content)
    
    def finalize(self, ctx: "DynamicRoundContext") -> ObservationReport:
        """Return the final narrative."""
        return ObservationReport(
            observer_name=self.name,
            metrics={"iteration_count": len(self._iteration_notes)},
            narrative=self._running_summary or " | ".join(self._iteration_notes),
        )


def save_observations(reports: List[ObservationReport], path: str) -> None:
    """Save observation reports to JSON for post-processing."""
    data = {
        "observations": [r.to_dict() for r in reports]
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


class HealthCheckObserver:
    """
    Watches for pathological behavior during a debate round.
    Flags issues like early mutual PASS, high validation failures, or zero bets.
    """
    
    @property
    def name(self) -> str:
        return "health_check"
        
    def on_iteration(self, ctx: "DynamicRoundContext", iteration: int) -> None:
        pass  # Checks are done at finalize

    def finalize(self, ctx: "DynamicRoundContext") -> ObservationReport:
        flags = []
        
        # 1. ALL_PASS
        if ctx.iterations_completed == 1 and ctx.decision_a and ctx.decision_a.bet_type.value == "pass" and ctx.decision_b and ctx.decision_b.bet_type.value == "pass":
            flags.append("ALL_PASS")
            
        # 2. HIGH_VALIDATION_FAILURE
        total_actions = ctx.iterations_completed * 2
        total_failures = ctx.validation_fallback_a + ctx.validation_fallback_b
        if total_actions > 0 and (total_failures / total_actions) >= 0.5:
            flags.append("HIGH_VALIDATION_FAILURE")
            
        # 3. ZERO_BETS
        if ctx.bet_count_a == 0 and ctx.bet_count_b == 0:
            flags.append("ZERO_BETS")
            
        narrative = "Health check OK."
        if flags:
            narrative = f"⚠️ WARNING: Pathological behaviors detected: {', '.join(flags)}"
            print(f"[{self.name}] {narrative}")
            
        return ObservationReport(
            observer_name=self.name,
            metrics={
                "flags_raised": flags, 
                "validation_failure_rate": total_failures / max(1, total_actions)
            },
            narrative=narrative,
        )
