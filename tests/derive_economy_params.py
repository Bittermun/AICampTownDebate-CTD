#!/usr/bin/env python3
"""Derive economy parameters from survival-runway assumptions."""
import argparse
import json
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.economy.calibration import CalibrationInputs, derive_economy_params


def main() -> int:
    parser = argparse.ArgumentParser(description="Derive economy parameters")
    parser.add_argument("--survival-rounds", type=int, default=6)
    parser.add_argument("--avg-generation-cost", type=float, default=30.0)
    parser.add_argument("--avg-bet-size", type=float, default=20.0)
    parser.add_argument("--avg-fee-rate", type=float, default=0.15)
    parser.add_argument("--edge-win-rate", type=float, default=0.60)
    parser.add_argument("--reserve-rounds", type=float, default=1.0)
    parser.add_argument("--output", default="logs/economy_calibration.json")
    args = parser.parse_args()

    result = derive_economy_params(
        CalibrationInputs(
            target_survival_rounds=args.survival_rounds,
            avg_generation_cost=args.avg_generation_cost,
            avg_bet_size=args.avg_bet_size,
            avg_fee_rate=args.avg_fee_rate,
            edge_win_rate=args.edge_win_rate,
            reserve_rounds=args.reserve_rounds,
        )
    )

    print("Derived economy parameters:")
    print(f"  initial_balance: {result.initial_balance}")
    print(f"  max_debt: {result.max_debt}")
    print(f"  tokens_per_round: {result.tokens_per_round}")
    print(f"  betting_fee_start: {result.betting_fee_start}")
    print(f"  betting_fee_cap: {result.betting_fee_cap}")

    print("\nSuggested YAML block:")
    print("economy:")
    print(f"  initial_balance: {result.initial_balance}")
    print(f"  max_debt: {result.max_debt}")
    print(f"  tokens_per_round: {result.tokens_per_round}")

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    print(f"\nSaved: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
