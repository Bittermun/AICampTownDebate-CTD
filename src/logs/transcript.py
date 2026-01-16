"""
Transcript Logger: Captures full debate content for analysis.
"""
import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Turn:
    speaker: str
    content: str
    turn_type: str  # "argument", "counter", "judgment"
    round_id: int
    tokens_bet: float = 0.0
    confidence: Optional[float] = None


@dataclass
class RoundTranscript:
    round_id: int
    topic: str
    turns: list[Turn] = field(default_factory=list)
    confidence_a: float = 0.0
    confidence_b: float = 0.0
    tokens_awarded_a: float = 0.0
    tokens_awarded_b: float = 0.0
    
    def add_argument(self, speaker: str, content: str, is_counter: bool = False, tokens_bet: float = 0.0):
        self.turns.append(Turn(
            speaker=speaker,
            content=content,
            turn_type="counter" if is_counter else "argument",
            round_id=self.round_id,
            tokens_bet=tokens_bet,
        ))
    
    def add_deliberation(self, speaker: str, decision: str, amount: float, reasoning: str):
        """Add debater's strategic deliberation (REFUTE/RESEARCH/PASS)."""
        content = f"**Decision**: {decision.upper()} (bet: {amount:.1f} tokens)\n**Reasoning**: {reasoning}"
        self.turns.append(Turn(
            speaker=speaker,
            content=content,
            turn_type="deliberation",
            round_id=self.round_id,
            tokens_bet=amount,
        ))
    
    def add_judgment(self, judge_id: str, reasoning: str, conf_a: float, conf_b: float):
        self.confidence_a = conf_a
        self.confidence_b = conf_b
        self.turns.append(Turn(
            speaker=judge_id,
            content=reasoning,
            turn_type="judgment",
            round_id=self.round_id,
            confidence=conf_a,
        ))
    
    def add_bet_resolution(self, speaker: str, won: bool, payout: float):
        """Add record of bet outcome."""
        status = "WON" if won else "LOST"
        content = f"**Bet Outcome**: {status}\n**Payout**: {payout:+.1f} tokens"
        self.turns.append(Turn(
            speaker=speaker,
            content=content,
            turn_type="payout",
            round_id=self.round_id,
            tokens_bet=payout if won else 0,
        ))


@dataclass
class DebateTranscript:
    tournament_id: str
    started_at: str
    config: dict
    rounds: list[RoundTranscript] = field(default_factory=list)
    final_balances: dict = field(default_factory=dict)
    winner: Optional[str] = None
    ended_at: Optional[str] = None
    
    def new_round(self, round_id: int, topic: str) -> RoundTranscript:
        rt = RoundTranscript(round_id=round_id, topic=topic)
        self.rounds.append(rt)
        return rt
    
    def finalize(self, winner: Optional[str], balances: dict):
        self.winner = winner
        self.final_balances = balances
        self.ended_at = datetime.now().isoformat()
    
    def save(self, path: str):
        """Save full transcript to JSON."""
        data = {
            "tournament_id": self.tournament_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "config": self.config,
            "winner": self.winner,
            "final_balances": self.final_balances,
            "rounds": [
                {
                    "round_id": r.round_id,
                    "topic": r.topic,
                    "confidence_a": r.confidence_a,
                    "confidence_b": r.confidence_b,
                    "tokens_awarded_a": r.tokens_awarded_a,
                    "tokens_awarded_b": r.tokens_awarded_b,
                    "turns": [
                        {
                            "speaker": t.speaker,
                            "type": t.turn_type,
                            "content": t.content,
                            "tokens_bet": t.tokens_bet,
                            "confidence": t.confidence,
                        }
                        for t in r.turns
                    ],
                }
                for r in self.rounds
            ],
        }
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def save_markdown(self, path: str):
        """Save human-readable transcript as Markdown."""
        lines = [
            f"# Debate Transcript: {self.tournament_id}",
            f"*Started: {self.started_at}*",
            f"*Ended: {self.ended_at}*",
            "",
            "## Configuration",
            f"```json",
            json.dumps(self.config, indent=2),
            "```",
            "",
        ]
        
        for r in self.rounds:
            lines.append(f"## Round {r.round_id}: {r.topic}")
            lines.append("")
            
            for t in r.turns:
                if t.turn_type == "judgment":
                    lines.append(f"### 🧑‍⚖️ {t.speaker} (Judgment)")
                    lines.append(f"**Confidence A**: {r.confidence_a:.2f} | **Confidence B**: {r.confidence_b:.2f}")
                elif t.turn_type == "deliberation":
                    lines.append(f"### 🎯 {t.speaker} (Strategic Deliberation)")
                elif t.turn_type == "payout":
                    lines.append(f"### 💰 {t.speaker} (Bet Resolution)")
                else:
                    emoji = "🔄" if t.turn_type == "counter" else "💬"
                    bet_info = f" (bet: {t.tokens_bet:.1f} tokens)" if t.tokens_bet > 0 else ""
                    lines.append(f"### {emoji} {t.speaker}{bet_info}")
                
                lines.append("")
                lines.append(t.content)
                lines.append("")
            
            lines.append(f"**Tokens awarded**: A={r.tokens_awarded_a:.1f}, B={r.tokens_awarded_b:.1f}")
            lines.append("")
            lines.append("---")
            lines.append("")
        
        lines.append("## Final Results")
        lines.append(f"**Winner**: {self.winner or 'TIE'}")
        lines.append("")
        for name, balance in self.final_balances.items():
            lines.append(f"- {name}: {balance:.1f} tokens")
        
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))


def create_transcript(config: dict) -> DebateTranscript:
    """Create a new transcript for a tournament."""
    return DebateTranscript(
        tournament_id=datetime.now().strftime("%Y%m%d_%H%M%S"),
        started_at=datetime.now().isoformat(),
        config=config,
    )
