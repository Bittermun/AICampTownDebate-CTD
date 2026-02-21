#!/usr/bin/env python3
"""
Trajectory Parser
Parses debate transcripts to measure internal reasoning (mesa-cognition)
and economic constraint awareness over time.

Extracts:
- Max Budget authorizations (from deliberation)
- Thinking Word Count (from generation)
- Output Word Count (from generation)
- Strategy shifts (Decisions)
"""
import sys
import re
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict

@dataclass
class DebaterTrajectory:
    name: str
    iterations: List[dict] = field(default_factory=list)

def parse_transcript(file_path: str):
    path = Path(file_path)
    if not path.exists():
        print(f"Error: Transcript {file_path} not found.")
        sys.exit(1)
        
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
        
    # Split by turn headers
    # Markers: ### 🎯 (Deliberation), ### 💬 (Initial/Research), ### 🔄 (Counter)
    turns = re.split(r'(### [🎯💬🔄] [^\n]+)', content)
    
    trajectories: Dict[str, DebaterTrajectory] = {}
    
    # We maintain a state of the "last deliberation" for each debater
    # to link the max_budget to the subsequent generation.
    pending_deliberations = {}
    
    for i in range(1, len(turns), 2):
        header = turns[i].strip()
        body = turns[i+1].strip() if i+1 < len(turns) else ""
        
        # Extract debater name
        match = re.search(r'### [🎯💬🔄]\s+([^\s(]+)', header)
        if not match:
            continue
            
        debater_name = match.group(1)
        if debater_name not in trajectories:
            trajectories[debater_name] = DebaterTrajectory(name=debater_name)
            
        if "🎯" in header:
            # Parse Deliberation
            decision_match = re.search(r'\*\*Decision\*\*: ([A-Z]+)', body)
            decision = decision_match.group(1) if decision_match else "UNKNOWN"
            
            budget_match = re.search(r'\*\*Max Budget\*\*: ([\d.]+) tokens', body)
            max_budget = float(budget_match.group(1)) if budget_match else 0.0
            
            pending_deliberations[debater_name] = {
                "decision": decision,
                "max_budget": max_budget
            }
            
        elif "💬" in header or "🔄" in header:
            # Parse Generation
            # Find all **Thinking:** blocks
            thinking_blocks = re.findall(r'\*\*Thinking:\*\*(.*?)(?=\n\n|\n\*\*|$)', body, re.DOTALL)
            thinking_text = " ".join(thinking_blocks).strip()
            
            # Remove thinking blocks to get just the output
            output_text = re.sub(r'\*\*Thinking:\*\*.*?(?=\n\n|\n\*\*|$)', '', body, flags=re.DOTALL).strip()
            
            think_words = len(thinking_text.split())
            out_words = len(output_text.split())
            
            # Retrieve linked deliberation
            linked_delib = pending_deliberations.get(debater_name, {"decision": "INITIAL", "max_budget": 0.0})
            
            trajectories[debater_name].iterations.append({
                "phase": linked_delib["decision"],
                "max_budget": linked_delib["max_budget"],
                "thinking_words": think_words,
                "output_words": out_words,
                "compression_ratio": (think_words / max(1, out_words))
            })
            
            # Clear pending deliberation so we don't reuse it accidentally
            pending_deliberations.pop(debater_name, None)
            
    _print_report(trajectories)

def _print_report(trajectories: Dict[str, DebaterTrajectory]):
    print("="*60)
    print("REASONING TRAJECTORY ANALYSIS")
    print("="*60)
    
    for name, traj in trajectories.items():
        print(f"\nDebater: {name}")
        print("-" * 50)
        print(f"{'Phase':<10} | {'Max Budget':<12} | {'Think Words':<12} | {'Out Words':<10} | {'Ratio (T/O)':<10}")
        print("-" * 50)
        
        for idx, iter_data in enumerate(traj.iterations):
            phase = iter_data["phase"]
            budget = f"{iter_data['max_budget']:.1f}"
            t_words = iter_data["thinking_words"]
            o_words = iter_data["output_words"]
            ratio = iter_data["compression_ratio"]
            
            # If ratio > 1, the model is thinking more than it is speaking (high compression)
            print(f"{phase:<10} | {budget:<12} | {t_words:<12} | {o_words:<10} | {ratio:.2f}")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python trajectory_parser.py <path_to_transcript.md>")
        sys.exit(1)
        
    parse_transcript(sys.argv[1])
