#!/usr/bin/env python3
"""
Comparative Lane Orchestrator.
Runs 3 specific benchmark lanes (full, emergent, baseline) and calculates paired reporting.
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# The three lanes we are comparing
LANES = {
    "full_economy": "configs/ollama_tournament_recommended.yaml",
    "emergent_stripped": "configs/emergent_base_config.yaml",
    "baseline_no_econ": "configs/baseline_no_econ_config.yaml",
}

def run_batch_for_lane(lane_name: str, config_path: str, args: argparse.Namespace, batch_timestamp: str):
    print(f"\n{'='*80}")
    print(f"Starting Lane: {lane_name} using config: {config_path}")
    print(f"{'='*80}")
    
    batch_id = f"comparative_{batch_timestamp}_{lane_name}"
    cmd = [
        sys.executable,
        "scripts/run_tournament_batch.py",
        "--config", config_path,
        "--runs", str(args.runs),
        "--start-seed", str(args.start_seed),
        "--seed-step", str(args.seed_step),
        "--batch-id", batch_id,
        "--output-root", args.output_root,
        "--concurrency", str(args.concurrency)
    ]
    
    if args.allow_stub:
        cmd.append("--allow-stub")
    if args.no_gate_judge_variance:
        cmd.append("--no-gate-judge-variance")
    if args.no_gate_judge_calibration:
        cmd.append("--no-gate-judge-calibration")
    if args.sleep_seconds > 0:
        cmd.extend(["--sleep-seconds", str(args.sleep_seconds)])
    if args.openai_base_urls:
        cmd.extend(["--openai-base-urls", args.openai_base_urls])
        
    proc = subprocess.run(cmd)
    if proc.returncode != 0:
        print(f"WARNING: Lane {lane_name} batch runner returned non-zero exit code: {proc.returncode}")
        
    manifest_path = Path(args.output_root) / batch_id / "batch_manifest.json"
    return manifest_path

def compute_comparative_report(manifests: dict, output_path: Path):
    print(f"\nComputing comparative report across {len(manifests)} lanes...")
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "lanes": list(manifests.keys()),
        "metrics": {}
    }
    
    # Load all manifests
    data = {}
    for lane, path in manifests.items():
        if not path.exists():
            print(f"Error: Manifest for {lane} not found at {path}")
            continue
        try:
            data[lane] = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"Error reading manifest for {lane}: {e}")
            continue
            
    # Extract keys we want to compare from aggregates
    metrics_to_compare = [
        "mean_rounds_completed",
        "mean_health_score",
        "mean_trace_count",
        "success_count"
    ]
    
    for metric in metrics_to_compare:
        report["metrics"][metric] = {}
        for lane, manifest in data.items():
            agg = manifest.get("aggregate", {})
            report["metrics"][metric][lane] = agg.get(metric, None)
            
    # Compute specific deltas (Full vs Baseline, Full vs Emergent)
    if "full_economy" in data:
        full_agg = data["full_economy"].get("aggregate", {})
        report["paired_deltas"] = {}
        
        for baseline_name in ["baseline_no_econ", "emergent_stripped"]:
            if baseline_name in data:
                base_agg = data[baseline_name].get("aggregate", {})
                
                # Check health_score delta
                h_full = full_agg.get("mean_health_score")
                h_base = base_agg.get("mean_health_score")
                if h_full is not None and h_base is not None:
                    report["paired_deltas"][f"health_uplift_over_{baseline_name}"] = round(h_full - h_base, 4)
                    
                # Pair the records by seed
                full_records = {r.get("seed"): r for r in data["full_economy"].get("records", [])}
                base_records = {r.get("seed"): r for r in data[baseline_name].get("records", [])}
                common_seeds = set(full_records.keys()).intersection(set(base_records.keys()))
                
                pass_rate_uplifts = []
                for seed in common_seeds:
                    fr = full_records[seed]
                    br = base_records[seed]
                    p_full = fr.get("pass_rate")
                    p_base = br.get("pass_rate")
                    if p_full is not None and p_base is not None:
                        pass_rate_uplifts.append(p_full - p_base)
                
                if pass_rate_uplifts:
                    avg_pass_rate_diff = sum(pass_rate_uplifts) / len(pass_rate_uplifts)
                    report["paired_deltas"][f"avg_pass_rate_diff_vs_{baseline_name}"] = round(avg_pass_rate_diff, 4)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Saved comparative report to: {output_path}")

def main():
    parser = argparse.ArgumentParser(description="Run multiple benchmark lanes and compare results.")
    parser.add_argument("--runs", type=int, default=3, help="Number of seeds to run per lane")
    parser.add_argument("--start-seed", type=int, default=101)
    parser.add_argument("--seed-step", type=int, default=1)
    parser.add_argument("--output-root", default="logs/comparative_batches")
    parser.add_argument("--allow-stub", action="store_true")
    parser.add_argument("--sleep-seconds", type=float, default=0.0)
    parser.add_argument("--concurrency", type=int, default=1)
    parser.add_argument("--no-gate-judge-variance", action="store_true")
    parser.add_argument("--no-gate-judge-calibration", action="store_true")
    parser.add_argument("--openai-base-urls", default="")
    args = parser.parse_args()

    batch_timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    
    manifest_paths = {}
    for lane_name, config_path in LANES.items():
        if not Path(config_path).exists():
            print(f"Error: Required config {config_path} for lane {lane_name} does not exist.")
            return 1
            
        manifest = run_batch_for_lane(lane_name, config_path, args, batch_timestamp)
        manifest_paths[lane_name] = manifest
        
    report_path = Path(args.output_root) / f"comparative_report_{batch_timestamp}.json"
    compute_comparative_report(manifest_paths, report_path)
    
    print("\nComparative Benchmark Execution Complete.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
