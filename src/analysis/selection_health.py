"""Selection Health Dashboard metrics for tournament artifacts."""
from __future__ import annotations

from dataclasses import dataclass
from math import log2
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional, Tuple
import re


@dataclass
class SelectionHealthReport:
    rounds_total: int
    bankruptcy_rate: float
    survival_runway_observed: float
    pass_rate: float
    aggression_rate: float
    mutual_pass_round_rate: float
    avg_iterations: float
    judge_score_entropy_bits: float
    judge_margin_mean: float
    judge_margin_stdev: float
    adaptation_gain_after_loss: float
    economy_reasoning_rate: float
    health_score: float

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rounds_total": self.rounds_total,
            "bankruptcy_rate": round(self.bankruptcy_rate, 4),
            "survival_runway_observed": round(self.survival_runway_observed, 4),
            "pass_rate": round(self.pass_rate, 4),
            "aggression_rate": round(self.aggression_rate, 4),
            "mutual_pass_round_rate": round(self.mutual_pass_round_rate, 4),
            "avg_iterations": round(self.avg_iterations, 4),
            "judge_score_entropy_bits": round(self.judge_score_entropy_bits, 4),
            "judge_margin_mean": round(self.judge_margin_mean, 4),
            "judge_margin_stdev": round(self.judge_margin_stdev, 4),
            "adaptation_gain_after_loss": round(self.adaptation_gain_after_loss, 4),
            "economy_reasoning_rate": round(self.economy_reasoning_rate, 4),
            "health_score": round(self.health_score, 4),
        }


def _extract_decision(content: str) -> Optional[str]:
    m = re.search(r"\*\*Decision\*\*:\s*(\w+)", content)
    if not m:
        return None
    return m.group(1).upper()


def _extract_iteration(content: str) -> Optional[int]:
    m = re.search(r"\[Iter\s+(\d+)\]", content)
    if not m:
        return None
    return int(m.group(1))


def _entropy(counts: List[int]) -> float:
    total = sum(counts)
    if total <= 0:
        return 0.0
    h = 0.0
    for c in counts:
        if c <= 0:
            continue
        p = c / total
        h -= p * log2(p)
    return h


def compute_selection_health(
    transcript: Dict[str, Any],
    results: Optional[Dict[str, Any]] = None,
    ledger: Optional[Dict[str, Any]] = None,
) -> SelectionHealthReport:
    rounds: List[Dict[str, Any]] = transcript.get("rounds", [])
    rounds_total = len(rounds)
    if rounds_total == 0:
        return SelectionHealthReport(
            rounds_total=0,
            bankruptcy_rate=0.0,
            survival_runway_observed=0.0,
            pass_rate=0.0,
            aggression_rate=0.0,
            mutual_pass_round_rate=0.0,
            avg_iterations=0.0,
            judge_score_entropy_bits=0.0,
            judge_margin_mean=0.0,
            judge_margin_stdev=0.0,
            adaptation_gain_after_loss=0.0,
            economy_reasoning_rate=0.0,
            health_score=0.0,
        )

    final_balances = (results or {}).get("final_balances") or transcript.get("final_balances", {})
    debaters = list(final_balances.keys()) if final_balances else []
    if not debaters:
        # Fallback to config names.
        cfg = transcript.get("config", {})
        da = cfg.get("debater_a")
        db = cfg.get("debater_b")
        debaters = [d for d in [da, db] if d]

    bankrupt_agents = [d for d in debaters if final_balances.get(d, 0.0) <= 0.0]
    bankruptcy_rate = (len(bankrupt_agents) / len(debaters)) if debaters else 0.0

    # Survival runway from ledger when available, fallback to final-balance approximation.
    survival_runway_observed = float(rounds_total)
    if debaters:
        survival_rounds: List[int] = []
        txs = (ledger or {}).get("transactions", []) if isinstance(ledger, dict) else []
        initial_balance = float((ledger or {}).get("initial_balance", 0.0)) if isinstance(ledger, dict) else 0.0
        if txs and initial_balance > 0:
            txs_sorted = sorted(txs, key=lambda t: (int(t.get("round", 0)), t.get("timestamp", "")))
            for d in debaters:
                bal = initial_balance
                eliminated_round: Optional[int] = None
                for t in txs_sorted:
                    amt = float(t.get("amount", 0.0))
                    if t.get("from") == d:
                        bal -= amt
                    if t.get("to") == d:
                        bal += amt
                    if bal <= 0 and eliminated_round is None:
                        eliminated_round = int(t.get("round", rounds_total))
                survival_rounds.append(eliminated_round if eliminated_round is not None else rounds_total)
        else:
            for d in debaters:
                survival_rounds.append(rounds_total if d not in bankrupt_agents else max(1, rounds_total - 1))

        survival_runway_observed = mean(survival_rounds) if survival_rounds else float(rounds_total)

    total_decisions = 0
    total_pass = 0
    total_respond = 0
    economy_reasoning_hits = 0
    mutual_pass_rounds = 0
    iter_counts: List[int] = []

    score_pairs: Dict[Tuple[float, float], int] = {}
    score_margins: List[float] = []

    # Track round confidence by speaker for adaptation-after-loss metric.
    speaker_conf_hist: Dict[str, List[float]] = {}

    econ_keywords = {
        "token", "tokens", "cost", "fee", "balance", "budget", "ev", "bankrupt", "stake", "payout"
    }

    for r in rounds:
        turns = r.get("turns", [])
        delib_turns = [t for t in turns if t.get("type") == "deliberation"]
        round_last_decision: Dict[str, str] = {}
        round_max_iter = 0

        for t in delib_turns:
            decision = _extract_decision(t.get("content", ""))
            if decision:
                total_decisions += 1
                round_last_decision[t.get("speaker", "unknown")] = decision
                if decision in {"PASS", "HOLD"}:
                    total_pass += 1
                elif decision == "RESPOND":
                    total_respond += 1
            lc = t.get("content", "").lower()
            if any(k in lc for k in econ_keywords):
                economy_reasoning_hits += 1

            it = _extract_iteration(t.get("content", ""))
            if it:
                round_max_iter = max(round_max_iter, it)

        if round_max_iter > 0:
            iter_counts.append(round_max_iter)

        if round_last_decision:
            # Treat HOLD as pass-equivalent for mutual-pass semantics.
            if all(d in {"PASS", "HOLD"} for d in round_last_decision.values()):
                mutual_pass_rounds += 1

        # Final judgment in round.
        judgments = [t for t in turns if t.get("type") == "judgment"]
        if judgments:
            j = judgments[-1]
            ca = float(j.get("confidence_a", r.get("confidence_a", 0.5)))
            cb = float(j.get("confidence_b", r.get("confidence_b", 0.5)))
            pair = (round(ca, 3), round(cb, 3))
            score_pairs[pair] = score_pairs.get(pair, 0) + 1
            score_margins.append(abs(ca - cb))

            # Infer speaker mapping from argument turns.
            arg_turns = [t for t in turns if t.get("type") == "argument"]
            if len(arg_turns) >= 2:
                s1 = arg_turns[0].get("speaker", "A")
                s2 = arg_turns[1].get("speaker", "B")
                speaker_conf_hist.setdefault(s1, []).append(ca)
                speaker_conf_hist.setdefault(s2, []).append(cb)

    pass_rate = (total_pass / total_decisions) if total_decisions else 0.0
    aggression_rate = (total_respond / total_decisions) if total_decisions else 0.0
    mutual_pass_round_rate = mutual_pass_rounds / rounds_total
    avg_iterations = mean(iter_counts) if iter_counts else 0.0

    judge_score_entropy_bits = _entropy(list(score_pairs.values()))
    judge_margin_mean = mean(score_margins) if score_margins else 0.0
    judge_margin_stdev = pstdev(score_margins) if len(score_margins) > 1 else 0.0

    # Adaptation after loss: after a round where speaker lost (confidence lower),
    # how much did confidence improve next round on average?
    adaptation_deltas: List[float] = []
    for speaker, confs in speaker_conf_hist.items():
        if len(confs) < 2:
            continue
        for i in range(len(confs) - 1):
            if confs[i] < 0.5:
                adaptation_deltas.append(confs[i + 1] - confs[i])
    adaptation_gain_after_loss = mean(adaptation_deltas) if adaptation_deltas else 0.0

    economy_reasoning_rate = economy_reasoning_hits / total_decisions if total_decisions else 0.0

    # Composite health score in [0, 1], tuned to reward non-degenerate behavior.
    #  - Prefer pass-rate around 0.35 (not always bet, not always pass)
    #  - Prefer score entropy > ~1.0 bit for richer signal
    #  - Prefer positive adaptation-after-loss
    pass_target = 0.35
    pass_component = max(0.0, 1.0 - abs(pass_rate - pass_target) / 0.35)
    entropy_component = min(1.0, judge_score_entropy_bits / 1.5)
    adapt_component = min(1.0, max(0.0, (adaptation_gain_after_loss + 0.05) / 0.10))
    bankruptcy_component = 1.0 - min(1.0, abs(bankruptcy_rate - 0.25) / 0.25)  # soft target ~25%
    health_score = 0.35 * pass_component + 0.3 * entropy_component + 0.25 * adapt_component + 0.1 * bankruptcy_component

    return SelectionHealthReport(
        rounds_total=rounds_total,
        bankruptcy_rate=bankruptcy_rate,
        survival_runway_observed=survival_runway_observed,
        pass_rate=pass_rate,
        aggression_rate=aggression_rate,
        mutual_pass_round_rate=mutual_pass_round_rate,
        avg_iterations=avg_iterations,
        judge_score_entropy_bits=judge_score_entropy_bits,
        judge_margin_mean=judge_margin_mean,
        judge_margin_stdev=judge_margin_stdev,
        adaptation_gain_after_loss=adaptation_gain_after_loss,
        economy_reasoning_rate=economy_reasoning_rate,
        health_score=health_score,
    )
