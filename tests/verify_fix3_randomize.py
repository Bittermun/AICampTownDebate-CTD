#!/usr/bin/env python3
"""Verify Fix 3: Randomize argument order is enabled."""
from src.config_loader import load_config

config = load_config("configs/tournament_config.yaml")

if config.randomize_argument_order:
    print("✅ randomize_argument_order is TRUE")
    print("   First-mover bias mitigation: ENABLED")
else:
    print("❌ randomize_argument_order is FALSE")
    print("   First-mover bias mitigation: DISABLED")
    exit(1)

print("\n✅✅✅ Fix 3 VERIFIED: Position bias mitigation enabled")
