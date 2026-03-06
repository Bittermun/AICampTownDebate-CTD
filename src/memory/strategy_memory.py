"""
Strategy Memory module for debaters.
Provides cross-round learning without weight updates by rendering a "Playbook"
of past round outcomes into the deliberation context window.
"""
from dataclasses import dataclass, asdict
import json
import re

@dataclass
class RoundMemory:
    round_id: int
    topic: str
    won: bool
    margin: float
    alloc_summary: str
    strategy_label: str

class StrategyMemory:
    def __init__(self, max_entries: int = 10):
        self.entries: list[RoundMemory] = []
        self.max_entries = max_entries

    def record_outcome(self, round_id: int, topic: str, confidence_self: float, confidence_opponent: float, judgment_reasoning: str = "", own_content: str = ""):
        """Record the outcome of a round to build the playbook."""
        won = confidence_self > confidence_opponent
        margin = abs(confidence_self - confidence_opponent)
        
        # Extract allocation breakdown from judgment
        alloc_summary = ""
        alloc_match = re.search(r"\[ALLOC\]\s*(.*?)(?:\s*\||$)", judgment_reasoning)
        if alloc_match:
            # Shorten "Acc: A=70%/B=30%, Resp: A=65%/B=35%, Dev: A=60%/B=40%" for brevity
            alloc = alloc_match.group(1).replace("Acc:", "Acc").replace("Resp:", "Resp").replace("Dev:", "Dev").replace(" ", "")
            alloc_summary = alloc
            
        # VERY basic heuristic for strategy label based on argument text or judgment
        # This gives the debater a vocabulary to reason about what works
        text_to_analyze = (own_content + " " + judgment_reasoning).lower()
        
        strategy_label = "general"
        if any(w in text_to_analyze for w in ["study", "data", "evidence", "empirical", "statistic", "percent"]):
            strategy_label = "empirical"
        elif any(w in text_to_analyze for w in ["moral", "right", "value", "ethical", "normative", "principle", "duty"]):
            strategy_label = "normative"
        elif any(w in text_to_analyze for w in ["pragmatic", "practical", "implement", "cost", "feasibl"]):
            strategy_label = "pragmatic"
        elif any(w in text_to_analyze for w in ["concede", "agree", "however", "valid point", "common ground"]):
            strategy_label = "concession-seeking"
            
        mem = RoundMemory(
            round_id=round_id,
            topic=topic,
            won=won,
            margin=margin,
            alloc_summary=alloc_summary,
            strategy_label=strategy_label
        )
        self.entries.append(mem)
        
        # Keep only the most recent N entries to avoid context bloat
        if len(self.entries) > self.max_entries:
            self.entries.pop(0)

    def render_playbook(self, max_lines: int = 5) -> str:
        """Render a concise playbook for the STATUS block."""
        if not self.entries:
            return ""
            
        lines = []
        # Render recent rounds (up to max_lines - 1)
        recent_entries = self.entries[-(max_lines - 1):]
        for e in recent_entries:
            result_str = f"WON (+{e.margin:.2f})" if e.won else f"LOST (-{e.margin:.2f})"
            alloc_str = f" | {e.alloc_summary}" if e.alloc_summary else ""
            lines.append(f"- R{e.round_id} '{e.topic[:20]}...': {result_str} — {e.strategy_label} framing{alloc_str}")
            
        # Calculate pattern / win rates
        strategy_stats = {}
        for e in self.entries:
            if e.strategy_label not in strategy_stats:
                strategy_stats[e.strategy_label] = {"w": 0, "l": 0}
            if e.won:
                strategy_stats[e.strategy_label]["w"] += 1
            else:
                strategy_stats[e.strategy_label]["l"] += 1
                
        # Find best strategy
        best_strategy = None
        best_winrate = -1.0
        for strat, stats in strategy_stats.items():
            total = stats["w"] + stats["l"]
            winrate = stats["w"] / total
            # Only consider patterns with at least 1 win
            if winrate > best_winrate and stats["w"] > 0:
                best_winrate = winrate
                best_strategy = strat
                
        if best_strategy:
            w = strategy_stats[best_strategy]["w"]
            l = strategy_stats[best_strategy]["l"]
            lines.append(f"- Pattern: '{best_strategy}' framing has {w}W/{l}L record.")
            
        return "\n".join(lines)

    def save(self, path: str):
        """Persist playbook to disk for veteran experiments."""
        data = [asdict(e) for e in self.entries]
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def load(self, path: str):
        """Load a saved playbook (makes this debater a veteran)."""
        with open(path) as f:
            data = json.load(f)
        for entry in data:
            self.entries.append(RoundMemory(**entry))
        if len(self.entries) > self.max_entries:
            self.entries = self.entries[-self.max_entries:]

    @property
    def win_rate(self) -> float:
        if not self.entries:
            return 0.0
        return sum(1 for e in self.entries if e.won) / len(self.entries)
