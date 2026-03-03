import argparse
import subprocess
import time
import os
from pathlib import Path
from datetime import datetime

def main():
    parser = argparse.ArgumentParser(description="Run a batch of tournaments")
    parser.add_argument("--runs", type=int, default=5, help="Number of tournaments to run")
    parser.add_argument("--config", type=str, required=True, help="Path to config file")
    parser.add_argument("--output-dir", type=str, default="logs/batch", help="Base output directory")
    # New argument to support Intel endpoint sharding from the other AI
    parser.add_argument("--openai-base-urls", type=str, default="", help="Comma-separated list of OpenAI-compatible base URLs for concurrent endpoint sharding (e.g. Arc and NPU servers)")
    args = parser.parse_args()

    base_dir = Path(args.output_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = base_dir / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)

    print(f"Starting batch of {args.runs} tournaments.")
    print(f"Config: {args.config}")
    print(f"Output directory: {run_dir}")
    if args.openai_base_urls:
        print(f"Endpoint Sharding: {args.openai_base_urls}")
    print("-" * 50)
    
    # Parse roster of URLs
    roster = [u.strip() for u in args.openai_base_urls.split(",")] if args.openai_base_urls else []

    for i in range(1, args.runs + 1):
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Starting Run {i}/{args.runs}...")
        
        output_prefix = f"run_{i:03d}"
        
        cmd = [
            "python", "demo_tournament.py",
            "--config", args.config,
            "--output-dir", str(run_dir),
            "--output-prefix", output_prefix,
            "--seed", str(int(time.time() * 1000) % 10000)
        ]
        
        env = os.environ.copy()
        
        if roster:
            # Round-robin assign an endpoint to this run
            assigned_url = roster[(i - 1) % len(roster)]
            env["OPENAI_COMPAT_BASE_URL"] = assigned_url
            print(f"  -> Assigned Endpoint: {assigned_url}")
        
        start_time = time.time()
        try:
            result = subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
            elapsed = time.time() - start_time
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Run {i} completed in {elapsed:.1f}s.")
            
            log_path = run_dir / f"{output_prefix}_console.log"
            with open(log_path, "w", encoding="utf-8") as f:
                f.write(result.stdout)
                
        except subprocess.CalledProcessError as e:
            elapsed = time.time() - start_time
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Run {i} FAILED after {elapsed:.1f}s.")
            print("Error output:")
            print(e.stdout[-1000:])
            print(e.stderr[-1000:])
            print("Aborting batch.")
            return

    print("-" * 50)
    print(f"Batch completed successfully. Logs saved to {run_dir}")

if __name__ == "__main__":
    main()
