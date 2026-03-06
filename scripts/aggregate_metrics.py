import os
import json
import glob
from collections import defaultdict
import statistics

TARGET_DIRS = [
    "logs/stable_campaign_125",
    "logs/test_tmp_training_contracts",
    "logs/benchmark_artifacts",
    "logs/20260303T200411Z",
    "logs/batch",
    "logs/evolution_campaign*"
]

results = defaultdict(list)

def safe_mean(vals):
    return statistics.mean(vals) if vals else 0.0

for d in TARGET_DIRS:
    # Use glob for the base directory as well to catch wildcards like evolution_campaign*
    base_dirs = glob.glob(d)
    for bd in base_dirs:
        if not os.path.exists(bd):
            continue
        
        # Find all selection health JSONs in this directory tree
        pattern = os.path.join(bd, "**", "*selection_health*.json")
        files = glob.glob(pattern, recursive=True)

        for f in files:
            try:
                with open(f, 'r', encoding='utf-8') as fh:
                    data = json.load(fh)

                metric = {
                    "health_score": data.get("health_score", 0.0),
                    "pass_rate": data.get("pass_rate", 0.0),
                    "econ_reasoning": data.get("economy_reasoning_rate", 0.0),
                    "avg_iter": data.get("avg_iterations", 0.0),
                    "bankruptcy_rate": data.get("bankruptcy_rate", 0.0)
                }
                results[d].append(metric)
            except Exception:
                pass

print("="*80)
print(f"{'Campaign':<35} | {'Runs':<5} | {'Health':<6} | {'Econ Reasoning':<14} | {'Pass Rate':<9} | {'Avg Iter':<8}")
print("-" * 80)

for campaign, metrics in results.items():
    if not metrics:
        continue
        
    count = len(metrics)
    avg_health = safe_mean([m["health_score"] for m in metrics])
    avg_econ = safe_mean([m["econ_reasoning"] for m in metrics])
    avg_pass = safe_mean([m["pass_rate"] for m in metrics])
    avg_iter = safe_mean([m["avg_iter"] for m in metrics])
    
    name = os.path.basename(campaign)
    print(f"{name:<35} | {count:<5} | {avg_health:<6.3f} | {avg_econ:>7.1%}        | {avg_pass:>7.1%}   | {avg_iter:<8.2f}")

print("="*80)
