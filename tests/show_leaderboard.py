#!/usr/bin/env python3
"""
Match Registry Leaderboard

Shows cross-session tournament results and summary statistics.

Usage:
    python tests/show_leaderboard.py
    python tests/show_leaderboard.py --limit 20
    python tests/show_leaderboard.py --stats
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.integrations.match_registry import MatchRegistry


def main():
    parser = argparse.ArgumentParser(description="Show match registry leaderboard")
    parser.add_argument("--limit", type=int, default=20, help="Number of runs to show")
    parser.add_argument("--stats", action="store_true", help="Show aggregate stats")
    args = parser.parse_args()

    registry = MatchRegistry()
    registry.print_leaderboard(limit=args.limit)

    if args.stats:
        stats = registry.summary_stats()
        if stats:
            print(f"\n  AGGREGATE STATS  ({stats.get('total_runs', 0)} total runs)")
            print(f"  Avg Health Score:   {stats.get('avg_health', 0):.3f}")
            print(f"  Avg Judge Margin:   {stats.get('avg_margin', 0):.3f}")
            print(f"  Avg Kelly Regret:   {stats.get('avg_kelly_regret', 0):.2f} tokens")
            print(f"  Avg Adaptation:     {stats.get('avg_adaptation', 0):+.3f}")


if __name__ == "__main__":
    main()
